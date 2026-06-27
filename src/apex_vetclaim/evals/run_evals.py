# Copyright 2026 Vector Research Labs. Apache-2.0.
"""Eval runner — runs the full eval suite against the live APEX VetClaim agent.

For each fixture:
1. Invokes the agent on the fixture's user_message
2. Captures the agent's response
3. Runs all 5 evals in parallel against that response
4. Records all scores

Aggregates results and writes a JSON report.

Usage:
    GOOGLE_CLOUD_PROJECT=apex-vetclaim GOOGLE_CLOUD_LOCATION=us-central1 \\
        uv run python -m apex_vetclaim.evals.run_evals

Output: prints a per-fixture and aggregate summary, writes the full report
to src/apex_vetclaim/evals/reports/<timestamp>.json
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from apex_vetclaim.agent import root_agent
from apex_vetclaim.evals.accuracy import evaluate_accuracy
from apex_vetclaim.evals.citation_integrity import evaluate_citation_integrity
from apex_vetclaim.evals.fidelity import evaluate_fidelity
from apex_vetclaim.evals.fixtures import FIXTURES
from apex_vetclaim.evals.safety import evaluate_safety
from apex_vetclaim.evals.specificity import evaluate_specificity

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


async def _run_agent(user_message: str) -> str:
    """Invoke the APEX VetClaim agent and return the final text response."""
    runner = InMemoryRunner(agent=root_agent, app_name="apex_vetclaim_eval")
    session = await runner.session_service.create_session(
        app_name="apex_vetclaim_eval", user_id="eval_runner"
    )
    user_msg = types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
    final_text = ""
    async for event in runner.run_async(
        user_id="eval_runner", session_id=session.id, new_message=user_msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text = part.text
    return final_text


async def _run_evals_for_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Run the agent on a fixture, then run all 5 evals against the response in parallel."""
    vet_id = fixture["vet_id"]
    user_message = fixture["user_message"]
    print(f"\n[{vet_id}] {fixture['description']}")
    print(f"  Running agent...")

    agent_response = await _run_agent(user_message)
    if not agent_response:
        print(f"  ⚠️  Agent returned empty response. Skipping evals.")
        return {
            "vet_id": vet_id,
            "description": fixture["description"],
            "user_message": user_message,
            "agent_response": "",
            "hero_failure": fixture["hero_failure"],
            "error": "agent returned empty response",
            "evals": {},
        }

    print(f"  Agent responded ({len(agent_response)} chars). Running 5 evals in parallel...")

    # All 5 evals in parallel — Pro grading Flash
    results = await asyncio.gather(
        evaluate_accuracy(user_message, agent_response, fixture["ground_truth_facts"]),
        evaluate_citation_integrity(user_message, agent_response),
        evaluate_safety(user_message, agent_response, fixture["safety_no_phrases"]),
        evaluate_fidelity(user_message, agent_response),
        evaluate_specificity(user_message, agent_response),
        return_exceptions=True,
    )

    eval_names = ["accuracy", "citation_integrity", "safety", "fidelity_to_vet_narrative", "specificity"]
    eval_results: dict[str, Any] = {}
    for name, result in zip(eval_names, results):
        if isinstance(result, Exception):
            eval_results[name] = {
                "verdict": "ERROR",
                "reasoning": f"{type(result).__name__}: {result}",
            }
        else:
            eval_results[name] = result

    # Print compact per-fixture summary
    for name in eval_names:
        verdict = eval_results[name].get("verdict", "?")
        is_failure = verdict in ("FAIL", "POOR", "ERROR")
        marker = "✗" if is_failure else "✓"
        print(f"    {marker} {name}: {verdict}")

    return {
        "vet_id": vet_id,
        "description": fixture["description"],
        "user_message": user_message,
        "agent_response": agent_response,
        "hero_failure": fixture["hero_failure"],
        "evals": eval_results,
    }


def _compute_aggregates(per_fixture: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute aggregate scores across all fixtures for each eval dimension."""
    binary_evals = ["accuracy", "citation_integrity", "safety"]
    graded_evals = ["fidelity_to_vet_narrative", "specificity"]
    grade_to_score = {"EXCELLENT": 1.0, "GOOD": 0.75, "FAIR": 0.5, "POOR": 0.25, "ERROR": 0.0}

    aggregates: dict[str, Any] = {}

    for name in binary_evals:
        verdicts = [f["evals"].get(name, {}).get("verdict", "ERROR") for f in per_fixture if f.get("evals")]
        passes = sum(1 for v in verdicts if v == "PASS")
        total = len(verdicts)
        aggregates[name] = {
            "type": "binary",
            "score": round(passes / total, 2) if total > 0 else 0.0,
            "passes": passes,
            "total": total,
        }

    for name in graded_evals:
        verdicts = [f["evals"].get(name, {}).get("verdict", "ERROR") for f in per_fixture if f.get("evals")]
        scores = [grade_to_score.get(v, 0.0) for v in verdicts]
        aggregates[name] = {
            "type": "graded",
            "score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "distribution": {grade: verdicts.count(grade) for grade in grade_to_score.keys() if verdicts.count(grade) > 0},
            "total": len(verdicts),
        }

    return aggregates


async def main() -> None:
    print("=" * 70)
    print("APEX VetClaim — Eval Run")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Model: {os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')} (agent)")
    print(f"Eval judge: {os.environ.get('EVAL_MODEL', 'gemini-2.5-pro')} (5 evals)")
    print(f"Fixtures: {len(FIXTURES)}")
    print("=" * 70)

    # Run all fixtures sequentially (each fixture's eval batch runs in parallel internally)
    per_fixture = []
    for fixture in FIXTURES:
        result = await _run_evals_for_fixture(fixture)
        per_fixture.append(result)

    aggregates = _compute_aggregates(per_fixture)

    # Print final summary
    print("\n" + "=" * 70)
    print("AGGREGATE SCORES")
    print("=" * 70)
    for name, agg in aggregates.items():
        if agg["type"] == "binary":
            print(f"  {name:35s} {agg['score']:.2f}  ({agg['passes']}/{agg['total']} pass)")
        else:
            dist_str = ", ".join(f"{g}={c}" for g, c in agg.get("distribution", {}).items())
            print(f"  {name:35s} {agg['score']:.2f}  ({dist_str})")

    # Highlight hero failure findings
    hero = next((f for f in per_fixture if f.get("hero_failure")), None)
    if hero and hero.get("evals"):
        print("\n" + "=" * 70)
        print("HERO ARTIFACT — engineered failure case")
        print("=" * 70)
        print(f"  Fixture: {hero['vet_id']} — {hero['description']}")
        for eval_name, eval_result in hero["evals"].items():
            verdict = eval_result.get("verdict", "?")
            marker = "✗" if verdict in ("FAIL", "POOR", "ERROR") else "✓"
            print(f"    {marker} {eval_name}: {verdict}")
            if verdict in ("FAIL", "POOR", "ERROR"):
                reasoning = eval_result.get("reasoning", "")[:200]
                print(f"        → {reasoning}")

    # Write JSON report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"eval_run_{timestamp}.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "agent_model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        "eval_model": os.environ.get("EVAL_MODEL", "gemini-2.5-pro"),
        "aggregates": aggregates,
        "per_fixture": per_fixture,
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\n📊 Full report: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
