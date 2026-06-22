# Copyright 2026 Vector Research Labs. Apache-2.0.
"""APEX VetClaim agent — Google ADK + Gemini 2.5 Flash + five tools."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from apex_vetclaim.instrumentation import setup_tracing
from apex_vetclaim.prompt import vetclaim_instruction
from apex_vetclaim.tools.check_rating_schedule import check_rating_schedule
from apex_vetclaim.tools.draft_personal_statement import draft_personal_statement
from apex_vetclaim.tools.evidence_gap_check import evidence_gap_check
from apex_vetclaim.tools.review_secondary_conditions import review_secondary_conditions
from apex_vetclaim.tools.search_va_precedent import search_va_precedent

# Allow `adk run apex_vetclaim` to pick up env from .env if present
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Use Vertex AI (matches APEX Approve hygiene)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.pop("GOOGLE_API_KEY", None)

setup_tracing()

_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    model=_model,
    name="apex_vetclaim_agent",
    instruction=vetclaim_instruction,
    tools=[
        FunctionTool(func=check_rating_schedule),
        FunctionTool(func=review_secondary_conditions),
        FunctionTool(func=evidence_gap_check),
        FunctionTool(func=draft_personal_statement),
        FunctionTool(func=search_va_precedent),
    ],
)
