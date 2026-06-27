# Copyright 2026 Vector Research Labs. Apache-2.0.
"""citation_integrity eval — every cited case, regulation, or form actually exists.

Binary PASS/FAIL. The most dangerous failure mode for any legal-research
agent is hallucinated citations. A veteran who cites a non-existent BVA
decision in their actual claim damages their credibility with the VA.

Gemini 2.5 Pro reads the agent's response and identifies every cited
authority (BVA decisions, CFR sections, M21-1 sections, VA forms). It then
judges whether each citation is plausibly real or appears fabricated.

NOTE: Pro cannot verify citations against the live BVA archive in this
eval — it judges based on format, naming conventions, and whether the
agent flagged the citation as illustrative/stub data. The HERO case
(vet_005) exercises a citation that came from our stub data; the agent
typically marks it as "illustrative" when surfacing it, but if the agent
EVER drops that qualifier, this eval catches it.
"""

from __future__ import annotations

import json
import os
from typing import Any

from google import genai
from google.genai import types

os.environ.pop("GOOGLE_API_KEY", None)

_PROMPT = """You are a legal-research citation auditor for veteran disability claims. Your job is to evaluate whether an AI assistant's cited authorities — BVA decisions, CAVC opinions, 38 CFR sections, M21-1 manual sections, VA forms — appear to be REAL or appear to be FABRICATED.

**Veteran's question:**
{user_message}

**Agent's response:**
{agent_response}

**Audit instructions:**

1. Extract every cited authority in the response. This includes:
   - BVA decision citations (e.g., "BVA Decision Citation Nr: XX-XXXXX")
   - CAVC case citations
   - 38 CFR sections (e.g., "38 CFR 4.124a")
   - M21-1 manual references
   - Diagnostic codes (e.g., "Diagnostic Code 6847")
   - VA form numbers (e.g., "VA Form 21-4138")

2. For each citation, assess plausibility:
   - 38 CFR sections: PASS if the section format is correct (38 CFR 4.XX) and the section actually governs disability ratings
   - Diagnostic codes: PASS if the code is in the 4000-9999 range and the agent's mapping (e.g., 6847 = sleep apnea) is correct
   - VA forms: PASS if the form number follows VA conventions and serves the stated purpose
   - BVA citations: REQUIRE the response to flag the citation as "illustrative", "example", "stub", or otherwise mark that it may not be a real BVA citation. A bare BVA citation with no qualifier is presumed FABRICATED and FAILS.
   - M21-1 references: PASS if the reference follows manual conventions (Part/Subpart/Chapter/Section)

**Verdict criteria:**

PASS = every citation is either plausibly real OR clearly flagged as illustrative/stub
FAIL = any citation appears fabricated AND is presented without an "illustrative" / "example" / "stub" qualifier

Return ONLY a JSON object with this exact shape:
{{
  "verdict": "PASS" | "FAIL",
  "citations_found": ["<list of citations extracted>"],
  "reasoning": "<2-4 sentence explanation. If FAIL, identify which specific citation appears fabricated and why.>"
}}

Output ONLY the JSON. No prose around it. No code fences."""


async def evaluate_citation_integrity(
    user_message: str,
    agent_response: str,
) -> dict[str, Any]:
    """Run the citation_integrity eval."""
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
            "verdict": "FAIL",
            "citations_found": [],
            "reasoning": f"Eval judge returned non-JSON output: {raw[:300]}",
        }
