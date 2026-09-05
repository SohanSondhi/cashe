# Browser acquisition

The orchestrator calls `run_bounded_browser` for financial workflow evidence when a source has no usable authorized developer API/MCP access, or when portal evidence is needed for corroboration. Its acquisition preference remains an LLM decision, informed by source capabilities and entitlements.

The browser uses OpenAI's Responses API to choose semantic actions over captured page text and visible controls. The application, independently of the model, enforces registered read URLs, exact origin/port, budgets, field citations, and completeness checks. It does not read BluePeak's Python fixtures to acquire evidence.

## Setup

Install application dependencies and Chromium:

```powershell
python -m pip install -e '.[dev]'
python -m playwright install chromium
```

Add `OPENAI_API_KEY` to the ignored `cashe/.env`. The browser uses `BROWSER_OPENAI_MODEL` when provided, otherwise `OPENAI_MODEL` (the application's existing default is `gpt-5.6-terra`). It uses OpenAI explicitly and never silently switches providers. The key is read when a browser run starts. No portal credentials are put in prompts, screenshots, or traces.

`BROWSER_EXECUTABLE_PATH` can point to an installed Chromium binary. Standard Playwright installations use `PLAYWRIGHT_BROWSERS_PATH` when configured. On the current workspace, Chromium is installed under `C:\Users\sohan\Cache\.playwright`; set that environment variable when running here. `BROWSER_TIMEOUT_SECONDS` defaults to 180, and the tool permits 1–50 browser actions.

Start the normal application and submit an investigation:

```powershell
python -m uvicorn cashe.main:app --host 127.0.0.1 --port 8000
```

The tool takes `source_id`, `invoice_number`, `goal`, optional `sop_id`, `step_budget`, and `required_checks`. Omit `sop_id` to use the current preferred approved procedure. Accounting assertions for customer, amount, and currency must already exist in the same investigation; the orchestrator's MCP acquisition supplies these. Missing or conflicting expectations leave verification incomplete rather than creating assumed facts.

## Evidence and review

Each visited page produces a PNG screenshot and captured visible-text JSON. The actual action trace and final acquisition report are additional artifacts. Files are created exclusively and hashed over their bytes. Field assertions cite the observed labelled value, page URL, and observation; screenshots are linked through `EvidenceLink`. Timeline assertions preserve the portal event's effective timestamp and the application's observation timestamp.

The tool returns verified, partial, blocked, timeout, no-progress, failed, or budget-exhausted outcomes. Required checks cannot be disabled by passing an empty list. Unrecognized checks fail explicitly. Partial evidence is retained, and records with unverified identity do not produce assertions attached to the requested invoice.

The BluePeak legal-entity mismatch is intentional. The agent preserves `Cashe Holdings LLC` as the portal's submitted entity; it does not overwrite the accounting entity or resolve the conflict. The orchestrator must pursue other authorized evidence and then assemble the human review packet.

Investigation events link to captures and screenshots. `/evidence/{id}` renders images or JSON; `/api/evidence/{id}/content` returns original bytes. `/sops` shows retained procedure versions, run outcomes, action counts, and proposed updates.

Only fully verified browser success can automatically promote a procedure revision. Earlier versions remain unchanged. On a repeat, approved semantic labels select a link only when it uniquely matches the current page and passes access checks; otherwise the model observes the current UI. This reduces exploratory model decisions without claiming that required browser navigation disappeared.

## Supported portal configuration

`cashe/browser/profiles.json` supplies the initial BluePeak profile. An operator can supply another file through `BROWSER_PROFILES_PATH`. Add a source registry entry with browser entitlement and read-only permission, then configure its entry path, exact read paths (`{record_id}` is substituted safely), assets, permitted GET query fields, required labelled fields, status vocabulary, and timeline total/end indicators.

The shipped runtime supports server-rendered HTML, observed links, single-field GET searches, and native details expansion. Page scripts, service workers, WebSockets, business mutation requests, arbitrary URLs/selectors, redirects, and downloads are blocked. This intentionally matches the controlled MVP portal. JavaScript-only portals, real authentication/MFA/session providers, file exports, and production portal connectors need additional explicitly bounded adapters; a profile alone does not implement those capabilities. Only the configured mock read-only identity is currently supported.

## Verification

```powershell
python -m pytest -q
python scripts/smoke_browser.py
```

The smoke command starts an isolated copy of the actual FastAPI app on a temporary local port, loads accounting evidence, runs the browser, repeats using learned SOP memory, changes the portal layout, and runs again. It checks evidence/SOP pages and writes its SQLite database, captures, and result report under `.cache/browser-smoke/`. It makes no voice calls and does not resolve the legal-entity conflict.

Without an OpenAI key, `python scripts/smoke_browser.py --scripted` runs the same Chromium acquisition and storage using an explicitly labelled validation decider. This validates the browser runtime and application integration; it does not establish live OpenAI navigation quality. The normal application has no scripted or fixture fallback.

## PRISM callbacks

Set `PRISMTRACE_ENABLED=true`, `APP_ENV=staging`, `PRISMTRACE_HOST`, `PRISMTRACE_PROJECT_ID`, and `PRISMTRACE_API_KEY`. `PRISMTRACE_ORG_ID` is reserved for account reads. Browser workflow, model decisions, and browser actions share the investigation ID through callbacks in `cashe/browser/tracing.py` and `runner.py`; handlers flush on success and error. Browser model requests do not use the older orchestrator client's custom trace POST.

For staging verification with an existing credential file:

```powershell
python scripts/smoke_browser.py --trace-env ../primary-ai-system/.env
```

The command checks the authenticated setup doctor before and after actual browser acquisition. It does not send a synthetic handshake or invoke paid intelligence analysis. Add `--scripted` to verify actual browser-tool tracing without an OpenAI key, and report that distinction explicitly.

Verified on 2026-09-05 with the validation decider: all three real-browser smoke
runs passed, including original evidence and SOP page rendering. Decision counts
were 4 initially, 1 on the SOP repeat, and 2 after relabelling; each used 4 browser
actions. PRISM confirmed three additional application traces for session
`inv-c42616e92eb6` at 18:30:27 UTC.

Live OpenAI navigation subsequently passed from the Cashe dashboard in session
`inv-1260d57b7eae`, producing 20 assertions and 15 artifacts in four actions.
The authenticated PRISM doctor confirmed seven live/application traces at
18:49:25 UTC. The browser status was verified; financial adjudication remains
separate.

To populate the normal UI, run the application and click **Test browser** on the
dashboard. Select BluePeak and invoice `INV-BP-2088`. The button starts a job via
`POST /api/browser-investigations`; results are available at the returned
investigation URL and `GET /api/investigations/{id}/evidence`. This uses the
normal SQLite store. The standalone smoke command deliberately uses an isolated
store and does not populate the normal dashboard.

Implementation references: [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [Playwright browser contexts](https://playwright.dev/python/docs/api/class-browsercontext).
