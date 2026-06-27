# Copyright 2026 Vector Research Labs. Apache-2.0.
"""accuracy eval — does the agent's response match published VA rating criteria?

Binary PASS/FAIL. Gemini 2.5 Pro reads the agent's response and the
ground_truth_facts from the fixture, and judges whether the response
accurately reflects the regulatory text.

This is the foundational eval — wrong rating criteria for a veteran's
condition is the highest-stakes failure mode. The VA's adjudicators will
not be lenient with a vet who cites the wrong diagnostic code or wrong
rating percentages in their claim.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from google import genai
from google.genai import types

# Pop AI Studio key so Vertex backend is used (matches APEX Approve hygiene)
os.environ.pop("GOOGLE_API_KEY", None)

_PROMPT = """You are a VA disability claims accuracy auditor. Your job is to evaluate whether an AI assistant's response to a veteran accurately reflects the VA's published rating criteria.

You are NOT evaluating tone, helpfulness, or completeness — only ACCURACY of the factual claims about VA regulations.

**Veteran's question:**
{user_message}

**Agent's response:**
{agent_response}

**Ground-truth facts the response should accurately convey:**
{ground_truth_facts}

**Evaluation criteria:**

For the response to PASS:
- It must accurately convey the ground-truth facts listed above (paraphrasing is fine; the substance must be correct)
- It must NOT contain factually wrong claims about rating percentages, diagnostic codes, CFR sections, or evidence requirements
- It is OK if the response contains additional accurate information beyond the ground-truth facts
- It is OK if the response uses different phrasing than the ground-truth facts, as long as the meaning is preserved

The response FAILS if:
- It states a wrong diagnostic code, wrong CFR section, or wrong rating percentage
- It misstates an evidence requirement (e.g., claims a particular letter is sufficient when the VA requires more)
- It contradicts a ground-truth fact above

Return ONLY a JSON object with this exact shape:
{{
  "verdict": "PASS" | "FAIL",
  "reasoning": "<2-4 sentence explanation citing the specific accuracy concern or confirming alignment with ground truth>"
}}

Output ONLY the JSON. No prose around it. No code fences."""


async def evaluate_accuracy(
    user_message: str,
    agent_response: str,
    ground_truth_facts: list[str],
) -> dict[str, Any]:
    """Run the accuracy eval. Returns {verdict: 'PASS'|'FAIL', reasoning: str}."""
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "apex-vetclaim"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    facts_str = "\n".join(f"- {f}" for f in ground_truth_facts)
    prompt = _PROMPT.format(
        user_message=user_message,
        agent_response=agent_response,
        ground_truth_facts=facts_str,
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
            "verdict": "FAIL",
            "reasoning": f"Eval judge returned non-JSON output: {raw[:300]}",
        }
