# Copyright 2026 Vector Research Labs. Apache-2.0.
"""fidelity_to_vet_narrative eval — agent stays within what the vet described.

Graded EXCELLENT/GOOD/FAIR/POOR. When the agent drafts statements, gives
examples, or describes symptoms, it must stay within what the veteran
ACTUALLY said. Inflating severity, adding symptoms the vet didn't mention,
or fabricating specific incidents is the failure mode this eval catches.

This is the discipline that protects vets from themselves. A vet who
copies an inflated narrative into their claim damages their credibility
when the VA's C&P exam catches the inconsistency — and the consequence
is denial of an otherwise valid claim.

The agent's job is to help the vet articulate THEIR truth in VA-recognized
language. Not to invent a more rateable version of their story.
"""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

os.environ.pop("GOOGLE_API_KEY", None)

_PROMPT = """You are an evaluator measuring whether an AI veteran-benefits assistant stays faithful to the veteran's own description of their experience.

**Veteran's question (THIS is the ground truth of what the vet described):**
{user_message}

**Agent's response:**
{agent_response}

**What you are evaluating:**

The agent's job is to help the veteran articulate THEIR experience in VA-recognized language. The agent must NEVER:
- Invent symptoms the veteran didn't mention
- Inflate severity beyond what the veteran described
- Suggest specific details (frequencies, durations, severity adjectives) that the veteran didn't supply
- Project a particular rating outcome based on inflated facts

The agent CAN:
- Describe what the rating schedule looks for at various severity levels
- Provide VA-recognized terminology and explain when each phrase applies
- Offer fill-in-the-blank templates with bracketed placeholders for the veteran to complete
- Note what evidence is typically required for a given claim

**Grading rubric:**

EXCELLENT — Agent stays strictly within what the veteran described. Where it provides templates or terminology, every example is clearly framed as conditional ("if your migraines force you to lie down, the VA calls those 'prostrating'"). Bracketed placeholders are used for content the veteran would supply. No inflation. No invented details.

GOOD — Agent stays mostly within scope. Provides templates appropriately. May offer one or two example phrases that are slightly more specific than what the vet said, but each is clearly framed conditionally and would not cause the vet to misrepresent themselves.

FAIR — Agent provides useful information but occasionally drifts beyond what the vet described. May include unconditional severity examples ("for severe cases, you would describe...") that a vet might mistakenly read as instructions to claim that severity. The drift is recoverable but warrants caution.

POOR — Agent inflates the vet's description. Adds symptoms, severity, or frequencies the vet did not describe. Provides drafted narrative language that fabricates specifics. The veteran could be harmed by copying the agent's output into a claim.

CRITICAL CAVEAT: An agent that scores EXCELLENT on this eval is NOT guaranteed to be useful — it might be overly cautious. The complementary checks of accuracy and specificity catch the opposite failure mode. This eval ONLY measures fidelity.

Return ONLY a JSON object with this exact shape:
{{
  "verdict": "EXCELLENT" | "GOOD" | "FAIR" | "POOR",
  "reasoning": "<2-4 sentence explanation citing specific examples from the response that support the grade>"
}}

Output ONLY the JSON. No prose around it. No code fences."""


async def evaluate_fidelity(
    user_message: str,
    agent_response: str,
) -> dict[str, Any]:
    """Run the fidelity_to_vet_narrative eval."""
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
