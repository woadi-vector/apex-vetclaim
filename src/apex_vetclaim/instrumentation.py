# Copyright 2026 Vector Research Labs. Apache-2.0.
"""Phoenix Cloud + OpenInference tracing for APEX VetClaim.

Mirrors the APEX Approve instrumentation pattern: Phoenix register at startup,
then explicit instrumentation of google-adk (for ADK auto-tracing of the
agent loop). The google-genai instrumentor is currently skipped due to a
module-path mismatch with newer google-genai versions; ADK's own
instrumentation captures the LLM calls our tools make via the ADK runtime.
Bare genai.Client calls inside tools surface as generic OTLP spans rather
than dedicated genai spans — acceptable cost for now.
"""

import logging
import os

from openinference.instrumentation.google_adk import GoogleADKInstrumentor
from phoenix.otel import register

log = logging.getLogger(__name__)

_instrumented = False


def setup_tracing() -> None:
    """Initialize Phoenix tracing + ADK instrumentation. Idempotent."""
    global _instrumented
    if _instrumented:
        return

    project = os.environ.get("PHOENIX_PROJECT_NAME", "apex-vetclaim")
    endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT")

    if not endpoint or not os.environ.get("PHOENIX_API_KEY"):
        log.warning("Phoenix not configured (missing endpoint or API key). Skipping tracing setup.")
        return

    register(project_name=project, endpoint=endpoint, set_global_tracer_provider=True)
    GoogleADKInstrumentor().instrument()
    _instrumented = True
    log.info(f"Phoenix tracing live for project '{project}' at {endpoint}")
