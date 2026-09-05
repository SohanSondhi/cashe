# Repository conventions

The backend database choice for the MVP is SQLite, as confirmed by the user.
The application uses SQLAlchemy with SQLite in `cashe/db.py`.
This repository contains the application and product documentation.
The separately instrumented Python scaffold and ElevenLabs caller are in the
sibling `../primary-ai-system` project; do not claim their integrations are wired
into this repository without checking the application call sites.

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

## Browser acquisition tracing

The application browser tool is now wired at `cashe/orchestrator/tools.py::tool_browser`
and `cashe/browser/service.py::acquire`. `cashe/browser/runner.py` wraps acquisition,
OpenAI Responses decisions, and browser read actions in callbacks from
`cashe/browser/tracing.py`, sharing the investigation ID and flushing on success/error.
Enable with `PRISMTRACE_ENABLED=true` and `APP_ENV=staging`; the three existing
PRISMTRACE host/project/key variables configure the handler. This integration is
local to this application and does not import the sibling scaffold.

`scripts/smoke_browser.py` verifies actual Chromium acquisition through an isolated
FastAPI application and SQLite store. `--scripted` explicitly uses validation
decisions; it verifies runtime/storage/tracing, not live OpenAI decision quality.
Use `--trace-env` with an existing staging credential file for authenticated doctor
checks before/after the real browser invocation. See `docs/browser-agent.md`.

Staging verification on 2026-09-05: session `inv-c42616e92eb6` completed three
actual Chromium acquisitions (default, SOP repeat, changed layout) with the
explicit validation decider. The authenticated doctor at 18:30:27 UTC reported
`credential_ok=true`, `live_connected=true`, `overall=connected`; live/application
trace counts increased from 3 to 6. This verifies browser-tool tracing and storage,
not live OpenAI navigation.

Live OpenAI browser acquisition was subsequently verified through the UI in
session `inv-1260d57b7eae`: four browser actions produced 20 assertions and 15
artifacts in the normal application store. At 18:49:25 UTC the authenticated
doctor reported `credential_ok=true`, `live_connected=true`, and seven live/app
traces. This verifies acquisition, not adjudication of the legal-entity conflict.
