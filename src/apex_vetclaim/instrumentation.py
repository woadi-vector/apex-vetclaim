# Copyright 2026 Vector Research Labs. Apache-2.0.
"""Phoenix Cloud + OpenInference tracing for APEX VetClaim.

Mirrors the APEX Approve instrumentation pattern: Phoenix register at startup,
then explicit instrumentation of google-adk (for ADK auto-tracing of the
agent loop). The google-genai instrumentor is currently skipped due to a
module-path mismatch with newer google-genai versions; ADK's own
instrumentation captures the LLM calls our tools make via the ADK runtime.
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
    base = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")

    if not base or not os.environ.get("PHOENIX_API_KEY"):
        log.warning("Phoenix not configured (missing endpoint or API key). Skipping tracing setup.")
        return

    # Phoenix expects the OTLP traces ingestion path. The workspace URL alone
    # (e.g. https://app.phoenix.arize.com/s/jason-wold) is NOT the trace endpoint
    # — traces have to go to <workspace>/v1/traces.
    traces_endpoint = base if base.endswith("/v1/traces") else f"{base}/v1/traces"

    register(
        project_name=project,
        endpoint=traces_endpoint,
        set_global_tracer_provider=True,
        batch=True,  # use BatchSpanProcessor to address the production warning
    )
    GoogleADKInstrumentor().instrument()
    _instrumented = True
    log.info(f"Phoenix tracing live for project '{project}' at {traces_endpoint}")
