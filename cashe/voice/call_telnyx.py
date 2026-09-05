"""Place an outbound Telnyx call via the local realtime_telnyx server.

  uvicorn cashe.voice.realtime_telnyx:app --host 0.0.0.0 --port 8080
  python -m cashe.voice.call_telnyx +1XXXXXXXXXX
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=True)


def destination_number(explicit: str | None = None) -> str:
    to = (
        explicit
        or os.getenv("VOICE_TO_NUMBER")
        or os.getenv("HARBORLINE_PHONE")
        or ""
    ).strip()
    if not to:
        return ""
    if not to.startswith("+"):
        digits = "".join(c for c in to if c.isdigit())[-10:]
        to = "+1" + digits
    return to


def trigger_call(to: str | None = None, base: str | None = None) -> dict:
    dest = destination_number(to)
    if not dest:
        return {"error": "missing_destination", "hint": "Pass +1… or set VOICE_TO_NUMBER"}
    url = (base or os.getenv("LOCAL_SERVER", "http://127.0.0.1:8080")).rstrip("/")
    try:
        response = httpx.post(f"{url}/call", json={"to": dest}, timeout=60.0)
    except httpx.HTTPError as exc:
        return {"error": "local_server_unreachable", "detail": str(exc), "base": url}
    body: dict | str
    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        body = response.text
    if not response.is_success:
        return {"error": "call_failed", "status_code": response.status_code, "body": body}
    return {"ok": True, "status_code": response.status_code, "body": body, "to": dest}


def main() -> None:
    to = sys.argv[1] if len(sys.argv) > 1 else ""
    result = trigger_call(to or None)
    if result.get("error"):
        print(json.dumps(result, indent=2))
        sys.exit(1)
    print(result.get("status_code"))
    print(json.dumps(result.get("body"), indent=2))


if __name__ == "__main__":
    main()
