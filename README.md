# Cashe

Evidence layer for the MONEY TALKS hackathon. Starts from an authoritative bank statement, then uses an LLM orchestrator to gather operational context from MCP, API, a bounded browser, and a voice caller.

## Run

```bash
uv sync
uv run playwright install chromium
uv run uvicorn cashe.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 and ask why cash decreased in September.

Full investigation against Prism (records demo human resolutions when the agent escalates):

```bash
uv run python -m cashe.demo
```

## Config

Copy `.env.example` to `.env`. `TAVILY_API_KEY` and `PRISM_API_KEY` are required for live research and the orchestrator. Tavily falls back to the committed cache if the live call fails.

The browser agent uses OpenAI (`OPENAI_API_KEY`) and Playwright to read the configured portal, capture screenshots and visible text, verify invoice identity and completeness, and store cited workflow assertions. Approved browser SOPs retain successful semantic navigation and can be reused across label/layout changes. See [browser setup and verification](docs/browser-agent.md).

Voice uses the pizza-agent telephony stack (Vapi, Bland, Telnyx, or Twilio). `place_voice_call` f-strings the call purpose, dials `VOICE_TO_NUMBER`, and returns the full transcript to the voice subagent. Without telephony credentials it falls back to the HarborLine fixture.

There is no hard-coded source router. The orchestrator decides which subagents to spawn; tools only enforce read-only entitlements.
