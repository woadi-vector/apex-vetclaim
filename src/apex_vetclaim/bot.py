# Copyright 2026 Vector Research Labs. Apache-2.0.
"""APEX VetClaim Slack bot — Bolt for Python in Socket Mode.

Receives slash commands, @mentions, and DMs in the Slack sandbox. For each
veteran message, invokes the APEX VetClaim ADK agent and posts the agent's
response back to Slack. The bot is a thin transport layer; the agent does
the actual work.

System flags. Veterans decide.
"""

import asyncio
import json
import logging
import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from apex_vetclaim.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])

# Bot user ID is fetched at startup so we can strip @mentions cleanly from
# message text before passing to the agent.
_BOT_USER_ID: str | None = None


def _strip_bot_mention(text: str, bot_user_id: str | None) -> str:
    """Remove the @bot-user-id mention from a message so the agent only sees
    what the veteran actually said."""
    if not bot_user_id:
        return text
    return re.sub(rf"<@{bot_user_id}>\s*", "", text).strip()


async def _run_agent(user_text: str) -> str:
    """Invoke the APEX VetClaim agent and return the final text response."""
    runner = InMemoryRunner(agent=root_agent, app_name="apex_vetclaim")
    session = await runner.session_service.create_session(
        app_name="apex_vetclaim", user_id="slack_user"
    )
    user_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_text)],
    )
    final_text = ""
    async for event in runner.run_async(
        user_id="slack_user", session_id=session.id, new_message=user_message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text = part.text
    return final_text or "(The agent returned no text. Try rephrasing your question.)"


def _split_text_for_blocks(text: str, chunk_size: int = 2900) -> list[str]:
    """Split text into Slack-safe chunks, preferring to break on paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > chunk_size:
        # Try to split on the last paragraph break before the limit
        split_at = remaining.rfind("\n\n", 0, chunk_size)
        if split_at == -1:
            # Fall back to last newline
            split_at = remaining.rfind("\n", 0, chunk_size)
        if split_at == -1 or split_at < chunk_size // 2:
            # Fall back to hard split
            split_at = chunk_size
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _agent_response_to_slack_blocks(user_text: str, agent_text: str) -> list[dict]:
    """Format the agent's response as Slack Block Kit. Long responses are split
    across multiple section blocks rather than truncated."""
    blocks = [
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":scroll: *Your question:* {user_text[:200]}{'...' if len(user_text) > 200 else ''}",
                }
            ],
        },
    ]
    for chunk in _split_text_for_blocks(agent_text, chunk_size=2900):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_APEX VetClaim surfaces information from the VA rating schedule. *It does not file claims, give legal advice, or replace a VSO.* Always confirm with an accredited VSO before acting on what you read here._",
                }
            ],
        }
    )
    return blocks


@app.command("/vetclaim")
def handle_vetclaim_command(ack, command, respond, client):
    """User typed /vetclaim <text> in a channel."""
    ack()
    user_question = (command.get("text") or "").strip()
    if not user_question:
        respond(
            text=(
                "Hi — I'm APEX VetClaim. Ask me anything about your VA "
                "disability rating, secondary conditions, or evidence "
                "you might need.\n\n"
                "*Try:* `/vetclaim What is the rating schedule for migraines?`"
            )
        )
        return

    # Acknowledge immediately so the slash command doesn't time out
    respond(text=":hourglass_flowing_sand: APEX VetClaim is reviewing your question (30-90 sec)...")

    # Run the agent and post the result back via response_url
    try:
        agent_response = asyncio.run(_run_agent(user_question))
    except Exception as e:
        log.exception("Agent run failed")
        respond(text=f":warning: The agent encountered an error: `{type(e).__name__}`. Try again, or rephrase your question.")
        return

    respond(blocks=_agent_response_to_slack_blocks(user_question, agent_response), text=agent_response[:200])


@app.event("app_mention")
def handle_app_mention(event, say, client):
    """Someone @-mentioned the bot in a channel."""
    user = event.get("user")
    channel = event.get("channel")
    raw_text = event.get("text", "")
    user_text = _strip_bot_mention(raw_text, _BOT_USER_ID)

    if not user_text:
        say(
            text=(
                f"Hi <@{user}> — I'm APEX VetClaim. Ask me about your VA "
                "disability rating, secondary conditions you might be missing, "
                "or evidence you'd need for a claim.\n\n"
                "*Try:* `@APEX VetClaim what's the rating schedule for migraines?`"
            )
        )
        return

    # Post a "thinking" message we can update with the agent's response
    thinking = client.chat_postMessage(
        channel=channel,
        text=f":hourglass_flowing_sand: <@{user}>, I'm reviewing your question (30-90 sec)...",
    )

    try:
        agent_response = asyncio.run(_run_agent(user_text))
    except Exception as e:
        log.exception("Agent run failed")
        client.chat_update(
            channel=channel,
            ts=thinking["ts"],
            text=f":warning: <@{user}>, the agent hit an error: `{type(e).__name__}`. Try rephrasing.",
        )
        return

    client.chat_update(
        channel=channel,
        ts=thinking["ts"],
        text=agent_response[:200],
        blocks=_agent_response_to_slack_blocks(user_text, agent_response),
    )


@app.event("message")
def handle_direct_message(event, say, client):
    """DMs to the bot."""
    if event.get("channel_type") != "im":
        return
    if event.get("bot_id") or event.get("subtype"):
        return  # ignore bot messages and edits

    user = event.get("user")
    user_text = event.get("text", "").strip()
    if not user_text:
        return

    log.info(f"DM from {user}: {user_text[:100]}")

    thinking = say(text=f":hourglass_flowing_sand: Reviewing your question (30-90 sec)...")

    try:
        agent_response = asyncio.run(_run_agent(user_text))
    except Exception as e:
        log.exception("Agent run failed")
        client.chat_update(
            channel=event["channel"],
            ts=thinking["ts"],
            text=f":warning: The agent hit an error: `{type(e).__name__}`. Try rephrasing.",
        )
        return

    client.chat_update(
        channel=event["channel"],
        ts=thinking["ts"],
        text=agent_response[:200],
        blocks=_agent_response_to_slack_blocks(user_text, agent_response),
    )


def main() -> None:
    global _BOT_USER_ID
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])

    # Resolve our own bot user ID for mention-stripping
    try:
        auth = app.client.auth_test()
        _BOT_USER_ID = auth["user_id"]
        log.info(f"Bot user ID: {_BOT_USER_ID}")
    except Exception as e:
        log.warning(f"Could not resolve bot user ID: {e}")

    log.info("APEX VetClaim starting in Socket Mode...")
    handler.start()


if __name__ == "__main__":
    main()
