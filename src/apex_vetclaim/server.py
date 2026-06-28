# Copyright 2026 Vector Research Labs. Apache-2.0.
"""FastAPI server wrapping the Slack bot for Cloud Run deployment.

Two surfaces sharing one agent:
- Slack Socket Mode bot runs in a background thread, holding a websocket to Slack
- FastAPI HTTP endpoints for Cloud Run health checks and direct agent invocation
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from apex_vetclaim.agent import root_agent
from google.adk.runners import InMemoryRunner
from google.genai import types

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _start_slack_bot_in_background() -> None:
    """Spawn the Slack Socket Mode bot in a daemon thread."""
    def _runner() -> None:
        try:
            from apex_vetclaim.bot import main as bot_main
            log.info("Starting Slack Socket Mode bot in background thread...")
            bot_main()
        except Exception:
            log.exception("Slack bot crashed in background thread")

    t = threading.Thread(target=_runner, name="slack-bot", daemon=True)
    t.start()
    log.info("Slack bot thread launched.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_slack_bot_in_background()
    yield
    log.info("FastAPI shutting down.")


app = FastAPI(
    title="APEX VetClaim",
    description="Slack agent for veteran disability triage. Primary surface: Slack. HTTP surface: this API.",
    version="0.1.0",
    lifespan=lifespan,
)


class TriageRequest(BaseModel):
    user_message: str
    user_id: str = "http_caller"


class TriageResponse(BaseModel):
    user_message: str
    agent_response: str
    model: str
    tools_called: list[str] = []


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "APEX VetClaim",
        "version": "0.1.0",
        "primary_surface": "Slack",
        "endpoints": {
            "GET /": "this identity payload",
            "GET /healthz": "liveness probe",
            "POST /triage": "invoke the agent (JSON: {user_message, user_id?})",
        },
        "principles": [
            "System flags. Veterans decide.",
            "Anchor every claim to specifics.",
            "Fidelity to the veteran's narrative.",
            "Default to 'consult a VSO' under uncertainty.",
        ],
        "disclaimer": "APEX VetClaim surfaces info from the VA rating schedule. It does not file claims, give legal advice, or replace a VSO.",
    }


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResponse)
async def triage(req: TriageRequest) -> TriageResponse:
    """Invoke the agent over HTTP. Same agent the Slack bot uses."""
    user_msg = (req.user_message or "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="user_message is required")
    if len(user_msg) > 4000:
        raise HTTPException(status_code=400, detail="user_message must be <= 4000 chars")

    runner = InMemoryRunner(agent=root_agent, app_name="apex_vetclaim_http")
    session = await runner.session_service.create_session(
        app_name="apex_vetclaim_http", user_id=req.user_id
    )
    message = types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])
    final_text = ""
    tools_called: list[str] = []
    async for event in runner.run_async(
        user_id=req.user_id, session_id=session.id, new_message=message
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text = part.text
                if hasattr(part, "function_call") and part.function_call:
                    name = getattr(part.function_call, "name", None)
                    if name and name not in tools_called:
                        tools_called.append(name)

    return TriageResponse(
        user_message=user_msg,
        agent_response=final_text or "(no text returned)",
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        tools_called=tools_called,
    )
