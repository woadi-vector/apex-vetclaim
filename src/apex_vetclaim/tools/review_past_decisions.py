# Copyright 2026 Vector Research Labs. Apache-2.0.
"""review_past_decisions — Phoenix MCP integration.

Queries the Arize Phoenix MCP server for recent traces in the apex-vetclaim
project, returning a summary the agent can use as additional context before
making a triage recommendation on a borderline veteran case.

This is the partner-MCP integration for the Arize hackathon track:
- Spawns @arizeai/phoenix-mcp as a subprocess via Node.js
- Communicates via JSON-RPC over stdio (the MCP standard transport)
- Calls the `list-traces` tool to fetch recent triage activity
- Returns a brief textual summary to the agent

The narrative role: when a veteran case is borderline (low confidence,
unusual condition combination, or appeal-related), the agent consults its
own past triage decisions before responding. The eval pipeline measures
whether that historical context actually improved the decision.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from google.adk.tools import ToolContext


def _call_phoenix_mcp(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Spawn Phoenix MCP server, perform handshake, invoke a tool, return result."""
    api_key = os.environ.get("PHOENIX_API_KEY")
    base_url = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "").rstrip("/")
    # Phoenix MCP wants the workspace URL, NOT the /v1/traces ingestion path.
    # If our endpoint has the trace suffix, strip it.
    if base_url.endswith("/v1/traces"):
        base_url = base_url[: -len("/v1/traces")]

    if not api_key or not base_url:
        raise RuntimeError(
            "PHOENIX_API_KEY and PHOENIX_COLLECTOR_ENDPOINT must be set"
        )

    # Prefer globally installed phoenix-mcp binary (faster cold start in container).
    # Fall back to npx for local dev.
    if shutil.which("phoenix-mcp"):
        cmd = ["phoenix-mcp", "--baseUrl", base_url, "--apiKey", api_key]
    else:
        cmd = ["npx", "-y", "@arizeai/phoenix-mcp@latest", "--baseUrl", base_url, "--apiKey", api_key]

    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    try:
        # MCP initialize handshake
        init_request = {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "apex-vetclaim", "version": "0.1.0"},
            },
        }
        proc.stdin.write(json.dumps(init_request) + "\n")
        proc.stdin.flush()
        _ = proc.stdout.readline()  # consume initialize response

        # Send initialized notification (required by MCP spec)
        initialized_notif = {
            "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
        }
        proc.stdin.write(json.dumps(initialized_notif) + "\n")
        proc.stdin.flush()

        # Call the requested tool
        call_request = {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        proc.stdin.write(json.dumps(call_request) + "\n")
        proc.stdin.flush()

        response_line = proc.stdout.readline()
        if not response_line:
            raise RuntimeError("Empty response from Phoenix MCP server")
        return json.loads(response_line)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _summarize_traces(mcp_response: dict[str, Any]) -> str:
    """Parse the MCP tool/call response and return a brief textual summary."""
    if "error" in mcp_response:
        err = mcp_response["error"]
        return (
            f"Phoenix MCP returned error {err.get('code', '?')}: "
            f"{err.get('message', 'unknown error')}. "
            "Proceeding without historical context; recommend defaulting to "
            "VSO consultation for safety."
        )

    result = mcp_response.get("result", {})
    content = result.get("content", [])

    if not content:
        return (
            "No prior triage traces found in apex-vetclaim project. "
            "This may be the first observed case of this type."
        )

    text_blocks = [c.get("text", "") for c in content if c.get("type") == "text"]
    raw_text = "\n".join(text_blocks).strip()

    if not raw_text:
        return "Phoenix MCP returned no readable trace summary."

    if len(raw_text) > 1500:
        raw_text = raw_text[:1500] + "...[truncated]"

    return raw_text


async def review_past_decisions(
    reason_for_review: str, tool_context: ToolContext
) -> str:
    """Query Phoenix MCP for recent veteran-triage traces in the apex-vetclaim project.

    Call this tool when the current veteran case is borderline — meaning ANY of:
    - The condition combination is unusual or hasn't been clearly described before
    - Your initial confidence after the first round of tools is below 0.7
    - The veteran is asking about an appeal, denial, or contested adjudication
    - Two tool results conflict (e.g., rating-schedule lookup unclear, secondary
      conditions ambiguous)

    Phoenix MCP returns a summary of recent triage traces. Use that summary as
    additional context — NOT as a verdict. The current veteran's specific facts
    still lead the recommendation. The historical context grounds your judgment
    in patterns rather than priors.

    Args:
      reason_for_review: One short sentence stating why you are reviewing past
        decisions (e.g., "Veteran is asking about denial of sleep apnea
        secondary to PTSD with no nexus letter" or "Unusual combination of
        ratings — radiculopathy with no documented EMG").
      tool_context: ADK tool context (unused).

    Returns:
      A brief textual summary of recent triage traces from Phoenix, prefixed
      with the reason for review. If Phoenix is unreachable, returns a
      fall-closed message recommending VSO consultation.
    """
    if not reason_for_review or len(reason_for_review.strip()) < 10:
        return (
            "REJECTED: reason_for_review missing or too vague. "
            "State explicitly why you want to consult historical patterns "
            "(e.g., 'borderline confidence' or 'unusual condition combination')."
        )

    try:
        mcp_response = _call_phoenix_mcp(
            tool_name="list-traces",
            arguments={
                "project_identifier": os.environ.get(
                    "PHOENIX_PROJECT_NAME", "apex-vetclaim"
                ),
                "limit": 20,
            },
        )
        summary = _summarize_traces(mcp_response)
        return (
            f"Reason for review: {reason_for_review}\n\n"
            f"Phoenix MCP — recent triage traces from apex-vetclaim project:\n{summary}"
        )
    except Exception as e:
        return (
            f"Phoenix MCP query failed: {type(e).__name__}. "
            f"Reason for review was: '{reason_for_review[:200]}'. "
            "Proceeding without historical context; recommend the veteran "
            "consult a VSO before relying on this triage."
        )
