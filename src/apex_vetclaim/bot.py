"""APEX VetClaim Slack bot — Bolt for Python in Socket Mode.

Day 1 scaffold: responds to /vetclaim commands and @mentions with a
placeholder message. Tool integration and agent logic come later.
"""
import logging
import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.command("/vetclaim")
def handle_vetclaim_command(ack, command, respond):
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
    respond(
        text=(
            f":memo: Received your question:\n> {user_question}\n\n"
            "*(Agent logic not wired yet — this is a scaffold response.)*"
        )
    )


@app.event("app_mention")
def handle_app_mention(event, say):
    """Someone @-mentioned the bot in a channel."""
    user = event.get("user")
    text = event.get("text", "")
    say(
        text=(
            f"Hi <@{user}> — I'm APEX VetClaim. I'm here to help you "
            "understand your VA disability rating, identify under-rated "
            "or commonly-missed secondary conditions, and walk through "
            "evidence gaps.\n\n"
            "I never auto-file claims. *System flags. You decide.*\n\n"
            "Try `/vetclaim <your question>` or DM me directly."
        )
    )


@app.event("message")
def handle_direct_message(event, say):
    """Catch-all for DMs and channel messages — for now just log."""
    if event.get("channel_type") != "im":
        return  # ignore channel messages, only handle DMs
    user = event.get("user")
    text = event.get("text", "")
    log.info(f"DM from {user}: {text}")
    say(
        text=(
            "Got your message. I'm in scaffold mode right now and "
            "the agent isn't wired up yet — but I see you. "
            "Use `/vetclaim` for now or try @mentioning me in a channel."
        )
    )


def main() -> None:
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    log.info("APEX VetClaim starting in Socket Mode...")
    handler.start()


if __name__ == "__main__":
    main()
