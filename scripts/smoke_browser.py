"""Run isolated browser acquisition against the actual FastAPI portal.

Default: live OpenAI navigation. --scripted uses a visibly labelled test decider
while still exercising Chromium, the application evidence store, and SOP reuse.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scripted", action="store_true")
    parser.add_argument("--trace-env", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    output = root / ".cache" / "browser-smoke" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    output.mkdir(parents=True)
    os.environ["CASHE_DB"] = str(output / "cashe.db")
    os.environ["ARTIFACT_DIR"] = str(output / "artifacts")
    if args.trace_env:
        from dotenv import dotenv_values
        for key, value in dotenv_values(args.trace_env).items():
            if value and (key.startswith("PRISMTRACE_") or key == "APP_ENV"):
                os.environ[key] = value
        os.environ["PRISMTRACE_ENABLED"] = "true"
        os.environ["APP_ENV"] = "staging"

    import httpx
    import uvicorn
    from cashe.config import settings
    from cashe.db import session
    from cashe.main import app
    from cashe.models import SourceRegistry
    from cashe.orchestrator.loop import start_investigation
    from cashe.orchestrator.tools import tool_browser, tool_query_mcp
    from cashe.browser.service import acquire

    def doctor():
        response = httpx.get(settings.prismtrace_host.rstrip("/") + "/api/setup-doctor",
                             params={"project_id": settings.prismtrace_project_id},
                             headers={"X-PRISMtrace-Key": settings.prismtrace_api_key}, timeout=20)
        response.raise_for_status()
        data = response.json()
        summary = {key: data.get(key) for key in ("overall", "credential_ok", "live_connected", "app_connected",
                                                 "live_trace_count", "app_trace_count", "blocked_step", "checked_at")}
        print("PRISM doctor:", json.dumps(summary), flush=True)
        if data.get("credential_ok") is not True:
            raise RuntimeError("PRISM credential verification failed")
        return summary

    if settings.prismtrace_enabled:
        before = doctor()
        (output / "doctor-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    if not args.scripted and not settings.openai_api_key:
        raise SystemExit("Set OPENAI_API_KEY in cashe/.env, then rerun this command.")
    decider = None
    if args.scripted:
        spec = importlib.util.spec_from_file_location("browser_test_support", root / "tests" / "test_browser.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        decider = module.visible_decider

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("staging_server_start_failed")
    results = []
    try:
        run_id = start_investigation("Browser staging: retrieve BluePeak status and complete rejection history")
        with session() as db:
            source = db.get(SourceRegistry, "bluepeak-vendor-center")
            source.base_url = f"http://127.0.0.1:{port}/mock/bluepeak"
            source.allowed_hosts = json.dumps(["127.0.0.1"])
            db.commit()
            tool_query_mcp(db, run_id, "get_invoice", {"invoice_number": "INV-BP-2088"})
            for mode in ("default", "default", "relabeled"):
                httpx.post(f"http://127.0.0.1:{port}/api/mock/bluepeak/layout-mode", json={"mode": mode}).raise_for_status()
                kwargs = dict(goal="Retrieve status, submitted legal entity, dispute reason and complete timeline for INV-BP-2088",
                              invoice_number="INV-BP-2088", step_budget=20)
                if args.scripted:
                    result = acquire(db, run_id, source, **kwargs, decider=decider)
                else:
                    result = tool_browser(db, run_id, source.source_id, **kwargs)
                payload = result.get("result", {})
                summary = {"mode": mode, "status": payload.get("status"), "decision_mode": payload.get("decision_mode"),
                           "steps_used": payload.get("steps_used"), "model_decisions": payload.get("model_decisions"),
                           "sop_actions": payload.get("sop_actions"), "artifact_id": result.get("artifact_id"),
                           "sop_used": result.get("sop_used"), "remaining_gaps": payload.get("remaining_gaps")}
                print(json.dumps(summary), flush=True)
                results.append(summary)
                if result.get("error"):
                    break
                for artifact_id in [result["artifact_id"], *payload["screenshots"]]:
                    response = httpx.get(f"http://127.0.0.1:{port}/evidence/{artifact_id}")
                    response.raise_for_status()
                httpx.get(f"http://127.0.0.1:{port}/sops").raise_for_status()
        (output / "results.json").write_text(json.dumps({"session_id": run_id, "runs": results}, indent=2), encoding="utf-8")
        if settings.prismtrace_enabled:
            after = doctor()
            (output / "doctor-after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
        print("Evidence directory:", output, flush=True)
        if len(results) != 3 or any(r["status"] != "verified" for r in results):
            raise SystemExit(1)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


if __name__ == "__main__":
    main()
