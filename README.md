# APEX VetClaim

> A Slack agent that helps veterans understand their VA disability rating, surface under-rated conditions, and navigate evidence gaps. Built for the Slack Agent Builder Challenge — **Slack Agent for Good** track.

**Status:** scaffold (Day 1)
**License:** Apache 2.0

## Operating principles

- **System flags. Veterans decide.** The agent never auto-files.
- **Anchor every claim to specifics.** Every recommendation cites a regulation or rating-schedule reference.
- **Default to "consult a VSO" under uncertainty.** Confidence below 0.7 routes to "talk to a Veterans Service Officer."
- **Fidelity to the vet's narrative.** The agent helps the veteran articulate their own experience accurately — it never inflates beyond what was said.

## Architecture (planned)

- Slack bot (Bolt for Python, Socket Mode) as the messaging surface
- External agent service (Python + Google ADK + Gemini 2.5 Flash on Vertex AI) running on Cloud Run
- Arize Phoenix MCP for observability and historical-trace consultation
- Five-tool agent loop: `check_rating_schedule`, `review_secondary_conditions`, `evidence_gap_check`, `draft_personal_statement`, `search_va_precedent`
- Five LLM-as-a-Judge evals (Gemini 2.5 Pro grading Gemini 2.5 Flash): accuracy, citation integrity, safety, fidelity to vet narrative, specificity

## Running locally (dev)

\`\`\`
uv sync
uv run python -m apex_vetclaim.bot
\`\`\`

Requires `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` environment variables.

## Built by

[Vector Research Labs, LLC](https://www.vectorresearchlabs.com)
