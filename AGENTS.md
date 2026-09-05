# Repository conventions

The backend database choice is PostgreSQL. Do not assume MongoDB or Databricks.
This repository currently contains product documentation, not application call sites.
The initial instrumented Python scaffold is in the sibling `../primary-ai-system`
project; do not claim its tracing is wired into this repository.

## PRISM operations

Use environment variables `PRISMTRACE_HOST`, `PRISMTRACE_PROJECT_ID`,
`PRISMTRACE_ORG_ID`, and `PRISMTRACE_API_KEY`. Authenticate every request with
`X-PRISMtrace-Key`, never Bearer. Never commit credentials; `.env` stays ignored
and `.env.example` contains key names only.

Start with GET `/api/setup-doctor?project_id=...`. Fix authentication before
continuing. Prefer free reads: traces, spans, score/metrics summaries, intelligence,
existing clusters, recommendations, and fired alerts. For failures, explicitly use
`status=failed`; separately inspect evaluation scores and alerts. Read intelligence
`coverage` first: traces can exist while intelligence analysis remains pending.
Use the same trace identifier for detail and span requests. Report only fetched
evidence, and distinguish staging activity from production behavior.

Before any paid endpoint (including GET `/api/intelligence/narrative`), obtain
current pricing from `/api/credits/catalog`, state the cost, and get an explicit
yes. Check the credit balance. For backfill, first read the quote and active-job
endpoints, obtain approval for the total quoted cost, and pass that approved
amount as `max_credits`. A 402 means insufficient credits: stop, do not retry or
route around it. Never infer permission to spend from a general investigation.

Whenever application agents, chains, graphs, tools, retrievers, or model entry
points are added, wire PRISM callbacks with a shared session ID, flush on success
and error, and document their locations here. Verify with a real staging invocation
and the authenticated doctor; a synthetic handshake is not live verification.
Use non-sensitive staging inputs. Production writes require explicit approval.
