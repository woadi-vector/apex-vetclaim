# Copyright 2026 Vector Research Labs. Apache-2.0.
"""evidence_gap_check — surface what evidence is typically required vs present.

Given a description of what evidence the veteran has, returns the standard
evidence categories the VA looks for in a claim, with notes on which are
present, which are missing, and what specifically to do about each gap.

This tool uses an LLM sub-call because the comparison between "what the vet
described having" and "what's required for a strong claim" requires semantic
matching that a deterministic dict can't do well. The Pro-grades-Flash eval
pipeline catches if this tool hallucinates evidence categories.
"""

from typing import Any

import os
from google import genai
from google.genai import types

# Pop the AI Studio key so the Vertex backend is used (same hygiene as
# APEX Approve).
os.environ.pop("GOOGLE_API_KEY", None)

_PROMPT = """You are a VA disability claims evidence specialist. Given a veteran's description of what evidence they have for a claim, identify gaps that would likely cause a denial or under-rating, and suggest exactly what to obtain.

Standard VA evidence categories for any disability claim:
1. CURRENT DIAGNOSIS — formal diagnosis from a qualified provider (within last 12-24 months ideal)
2. IN-SERVICE OCCURRENCE — service treatment records, deployment records, hazardous duty docs, MOS records showing the cause/exposure
3. NEXUS / MEDICAL OPINION — a statement from a physician explicitly tying the current condition to the in-service event (the most-commonly-missing piece)
4. CONTINUITY OF SYMPTOMS — documentation that the condition has persisted since service (or worsened over time)
5. FUNCTIONAL IMPACT — statements describing how the condition affects daily life, work, sleep, relationships
6. BUDDY STATEMENTS — corroboration from people who served with the vet or who can attest to ongoing symptoms

Claim being evaluated:
- Condition: {condition}
- Vet's description of evidence they have: {evidence_described}

Return a JSON object with this exact shape:
{{
  "claim": "<condition>",
  "evidence_present": ["<category>: <what the vet has>", ...],
  "evidence_missing": ["<category>: <what is missing and why it matters>", ...],
  "highest_priority_gap": "<the single most important thing for the vet to obtain to strengthen this claim>",
  "concrete_next_steps": ["<step 1>", "<step 2>", "<step 3>"]
}}

CRITICAL RULES:
- Only cite evidence categories the vet ACTUALLY described. Do not invent evidence they didn't mention.
- For evidence_missing, only flag categories that are genuinely missing — don't list everything-not-mentioned as missing.
- highest_priority_gap should usually be the nexus letter if missing, because that's the most common reason claims are denied.
- concrete_next_steps must be ACTIONABLE — "ask your sleep doctor for a nexus letter tying sleep apnea to PTSD medications" not "obtain medical evidence."

Output ONLY the JSON object. No prose around it. No code fences."""


async def evidence_gap_check(condition: str, evidence_described: str) -> dict[str, Any]:
    """Identify gaps between what the vet has and what's required.

    Args:
      condition: The condition being claimed (e.g., 'sleep apnea secondary to PTSD').
      evidence_described: What the vet says they have — in their own words.
        E.g., 'I have a CPAP prescription from 2019 and my PTSD is already
        rated at 50%, but I don't have a letter from my sleep doctor
        connecting them.'

    Returns:
      Dict with evidence_present, evidence_missing, highest_priority_gap,
      and concrete_next_steps.
    """
    if not condition or not evidence_described:
        return {
            "error": "Both 'condition' and 'evidence_described' are required.",
        }

    import json
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "apex-vetclaim"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    prompt = _PROMPT.format(condition=condition, evidence_described=evidence_described)
    response = await client.aio.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
    )

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "error": "Could not parse model output as JSON.",
            "raw_output": raw[:1000],
        }
