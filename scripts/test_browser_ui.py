"""Exercise the real dashboard button and retained evidence with the running UI."""

import argparse
import json
from pathlib import Path
import time

import httpx
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--trace-env", type=Path)
    args = parser.parse_args()

    def doctor():
        if not args.trace_env:
            return
        from dotenv import dotenv_values
        env = dotenv_values(args.trace_env)
        response = httpx.get(env["PRISMTRACE_HOST"].rstrip("/") + "/api/setup-doctor",
                             params={"project_id": env["PRISMTRACE_PROJECT_ID"]},
                             headers={"X-PRISMtrace-Key": env["PRISMTRACE_API_KEY"]}, timeout=20)
        response.raise_for_status()
        data = response.json()
        print("PRISM:", json.dumps({key: data.get(key) for key in
                                   ["credential_ok", "live_connected", "live_trace_count", "checked_at"]}), flush=True)
        assert data.get("credential_ok") is True

    doctor()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(args.base_url)
            page.get_by_role("button", name="Test browser", exact=True).click()
            page.wait_for_url("**/investigations/*")
            run_id = page.url.rsplit("/", 1)[1]
            print("Investigation:", page.url, flush=True)
            deadline = time.monotonic() + 200
            result = {}
            while time.monotonic() < deadline:
                result = httpx.get(f"{args.base_url}/api/investigations/{run_id}").json()
                if result["status"] in {"evidence_ready", "failed"}:
                    break
                time.sleep(1)
            evidence = httpx.get(f"{args.base_url}/api/investigations/{run_id}/evidence").json()
            print(json.dumps({"status": result.get("status"), "message": result.get("pause_reason"),
                              "assertions": len(evidence.get("assertions", [])),
                              "artifacts": len(evidence.get("artifacts", []))}), flush=True)
            page.wait_for_function("document.getElementById('status').textContent !== 'running'", timeout=10000)
            output = Path(__file__).resolve().parents[1] / ".cache" / "browser-ui" / run_id
            output.mkdir(parents=True)
            page.screenshot(path=str(output / "investigation.png"), full_page=True)
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            print("UI capture:", output / "investigation.png", flush=True)
            assert result.get("status") == "evidence_ready", result.get("pause_reason")
            assert page.locator("#browser-records tr").count() >= 10
            assert page.locator("#browser-screenshots img").count() >= 1
            assert not errors, errors
        finally:
            browser.close()
    doctor()


if __name__ == "__main__":
    main()
