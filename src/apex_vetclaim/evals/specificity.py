# Copyright 2026 Vector Research Labs. Apache-2.0.
"""specificity eval — every claim is anchored to a regulation or code.

Graded EXCELLENT/GOOD/FAIR/POOR. The agent's operating principle is
"anchor every claim to specifics" — every rating reference cites a CFR
section, every condition reference cites a diagnostic code, every
evidence requirement is concrete (not "medical documentation" but
"a sleep study showing AHI > 5 plus a nexus letter from a sleep
medicine specialist").

This eval ensures the agent doesn't drift into vague-up answers that
sound helpful but give the veteran nothing actionable. Compare:

  POOR: "There are different rating levels for migraines depending on
        severity. You may want to gather medical evidence."

  EXCELLENT: "Migraines are rated under 38 CFR 4.124a, diagnostic code
            8100. The 30% rating requires characteristic prostrating
            attacks averaging once a month over several months. Evidence
            typically includes a headache log and a current diagnosis
            from neurology."

A vet who reads the EXCELLENT response can act on it. A vet who reads
the POOR response has to do the research the agent should have done.
"""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

os.environ.pop("GOOGLE_API_KEY", None)

_PROMPT = """You are an evaluator measuring whether an AI veteran-benefits assistant anchors every claim to specifics.

**Veteran's question:**
{user_message}

**Agent's response:**
{agent_response}

**What you are evaluating:**

A useful veteran-benefits agent gives the vet specific, actionable information:
- Cites CFR sections (e.g., "38 CFR 4.124a") when discussing ratings
- Names diagnostic codes (e.g., "Diagnostic Code 8100") when discussing conditions
- Specifies evidence requirements concretely (e.g., "sleep study showing AHI > 5", not "medical documentation")
- References specific VA forms by number where applicable (e.g., "VA Form 21-4138")
- Quotes VA terminology and explains when each phrase applies (e.g., "'prostrating' means the veteran must lie down")

A LESS useful agent gives vague, generic information that requires the vet to do additional research to act on:
- "There are different rating levels"
- "You may need medical evidence"
- "The VA looks at various factors"
- "It depends on the severity"

**Grading rubric:**

EXCELLENT — Every substantive claim is anchored. CFR sections cited, diagnostic codes named, evidence requirements concrete, terminology defined. A veteran could act on the response without additional research.

GOOD — Most claims are anchored. May have one or two passages that vague-up where a specific citation would have been better, but the response overall gives the vet specific direction.

FAIR — Mixed. Some claims are anchored; others are vague. The vet has to chase down details for at least half the response to act on it.

POOR — The response is generally vague. Few or no citations. Generic phrases like "medical evidence" substitute for specific requirements. A vet would gain little actionable direction.

CRITICAL CAVEAT: Specificity is NOT the same as length. A short, surgical response with three correctly-cited authorities scores EXCELLENT. A long, padded response with no citations scores POOR. Prioritize density of specifics over volume.

Return ONLY a JSON object with this exact shape:
{{
  "verdict": "EXCELLENT" | "GOOD" | "FAIR" | "POOR",
  "reasoning": "<2-4 sentence explanation citing specific examples from the response that support the grade>"
}}

Output ONLY the JSON. No prose around it. No code fences."""


async def evaluate_specificity(
    user_message: str,
    agent_response: str,
) -> dict[str, Any]:
    """Run the specificity eval."""
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "apex-vetclaim"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    prompt = _PROMPT.format(
        user_message=user_message,
        agent_response=agent_response,
    )

    response = await client.aio.models.generate_content(
        model=os.environ.get("EVAL_MODEL", "gemini-2.5-pro"),
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
            "verdict": "POOR",
            "reasoning": f"Eval judge returned non-JSON output: {raw[:300]}",
        }
