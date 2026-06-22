# Copyright 2026 Vector Research Labs. Apache-2.0.
"""draft_personal_statement — generate a template the vet fills in themselves.

CRITICAL DESIGN RULE: this tool produces a STRUCTURE with prompts for what
the vet should fill in. It does NOT produce a polished narrative on behalf
of the vet. The agent's job is to help the vet articulate THEIR experience
in language the VA recognizes — never to invent symptoms or inflate severity
beyond what the vet described.

The Pro-grades-Flash 'fidelity to vet narrative' eval catches any drift
from this rule. If this tool's output adds severity language the vet didn't
use, the eval flags it.
"""

from typing import Any

import os
from google import genai
from google.genai import types

os.environ.pop("GOOGLE_API_KEY", None)

_PROMPT = """You are a VA claims writing coach. Your job is to help a veteran draft a personal statement for a disability claim by giving them a STRUCTURE with prompts they fill in themselves.

You DO NOT write the statement for them. You DO NOT add details they didn't describe. You DO NOT inflate severity. You give them a fill-in-the-blank template with VA-recognized terminology cues so they can describe their OWN experience accurately.

Condition being claimed: {condition}
What the vet has said so far: {vet_described}

Return a JSON object with this shape:
{{
  "template": "<a multi-paragraph fill-in-the-blank template with [BRACKETED PLACEHOLDERS] for the vet to fill in>",
  "va_recognized_phrases": [
    "<a phrase the VA looks for, with explanation of when it applies — e.g., 'prostrating attacks: use this if your migraines force you to lie down'>",
    ...
  ],
  "what_NOT_to_say": [
    "<things vets commonly say that hurt their claim — e.g., 'avoid saying it's fine most of the time — describe the worst episodes accurately'>",
    ...
  ],
  "honesty_check": "<one sentence reminder that the vet should only describe what they actually experience, not what they think will get them a higher rating>"
}}

CRITICAL RULES:
- The template must use placeholders like [DESCRIBE WHEN YOU FIRST NOTICED SYMPTOMS] — NOT pre-filled examples that the vet might mistakenly copy.
- Only include va_recognized_phrases that map to terminology in 38 CFR Part 4.
- The honesty_check must remind the vet that overstating hurts more than it helps (the VA's exam process catches inconsistencies).

Output ONLY the JSON object. No prose around it. No code fences."""


async def draft_personal_statement(condition: str, vet_described: str) -> dict[str, Any]:
    """Generate a fill-in-the-blank template for a personal statement.

    Args:
      condition: The condition being claimed (e.g., 'migraines', 'PTSD increase').
      vet_described: What the vet has said about their experience so far —
        in their own words.

    Returns:
      Dict with template (string with placeholders), va_recognized_phrases,
      what_NOT_to_say, and honesty_check.
    """
    if not condition or not vet_described:
        return {
            "error": "Both 'condition' and 'vet_described' are required.",
        }

    import json
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("GOOGLE_CLOUD_PROJECT", "apex-vetclaim"),
        location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
    )

    prompt = _PROMPT.format(condition=condition, vet_described=vet_described)
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
