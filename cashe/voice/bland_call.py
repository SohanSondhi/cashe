"""Outbound Cashe collections call via Bland.ai (AI = collections caller)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from cashe.voice.realtime_common import (
    caller_name,
    collections_first_message,
    collections_instructions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=False)

API = "https://api.bland.ai/v1/calls"
TERMINAL_STATUSES = {"completed", "failed", "error", "canceled", "cancelled", "ended"}
POLL_TIMEOUT_S = 90.0
POLL_INTERVAL_S = 2.5


def _err(message: str, **extra) -> dict:
    return {"error": message, **extra}


def _headers() -> dict[str, str]:
    key = os.getenv("BLAND_API_KEY", "").strip()
    return {
        "authorization": key,
        "Content-Type": "application/json",
    }


def _normalize_e164(number: str) -> str:
    to_number = (number or "").strip()
    if not to_number:
        return ""
    if not to_number.startswith("+"):
        to_number = "+1" + "".join(c for c in to_number if c.isdigit())[-10:]
    return to_number


def task_prompt(objective: str | None = None, allowed_questions: list[str] | None = None) -> str:
    name = caller_name()
    phone = os.getenv("CUSTOMER_PHONE", "")
    base = collections_instructions(objective, allowed_questions)
    return f"""
{base}

SPEECH STYLE (sound human)
- Use contractions: I'm, I'll, that's, gonna, yeah.
- Keep answers SHORT (half a sentence to one sentence). Let them talk.
- Never say: "Certainly", "Absolutely", "As an AI", "How may I help".
- Never narrate ("I am now confirming..."). Just talk.

CALL SCREENING
- If "record your name and reason": say "{name}, returning a call." Stay on the line.
- Callback phone: {phone or "offer to repeat it if needed"}
""".strip()


def place_call(
    to_number: str,
    objective: str | None = None,
    allowed_questions: list[str] | None = None,
) -> dict:
    key = os.getenv("BLAND_API_KEY", "").strip()
    if not key:
        return _err("missing_bland_api_key")
    dest = _normalize_e164(to_number)
    if not dest:
        return _err("missing_destination")

    payload = {
        "phone_number": dest,
        "task": task_prompt(objective, allowed_questions),
        "first_sentence": collections_first_message(objective),
        "voice": os.getenv("BLAND_VOICE", "josh"),
        "model": os.getenv("BLAND_MODEL", "base"),
        "language": "en-US",
        "temperature": float(os.getenv("BLAND_TEMPERATURE", "0.7")),
        "wait_for_greeting": False,
        "record": True,
        "max_duration": int(os.getenv("BLAND_MAX_DURATION", "10")),
        "interruption_threshold": int(os.getenv("BLAND_INTERRUPTION_THRESHOLD", "150")),
        "voice_settings": {
            "speed": float(os.getenv("BLAND_VOICE_SPEED", "0.95")),
        },
    }
    try:
        response = httpx.post(API, headers=_headers(), json=payload, timeout=60)
    except httpx.HTTPError as exc:
        return _err("bland_call_failed", detail=str(exc))
    if not response.is_success:
        return _err("bland_call_failed", status_code=response.status_code, body=response.text[:500])
    body = response.json()
    return {
        "ok": True,
        "call": body,
        "id": body.get("call_id") or body.get("id"),
        "status": body.get("status"),
    }


def get_call(call_id: str) -> dict:
    if not os.getenv("BLAND_API_KEY", "").strip():
        return _err("missing_bland_api_key")
    try:
        response = httpx.get(f"{API}/{call_id}", headers=_headers(), timeout=30)
    except httpx.HTTPError as exc:
        return _err("bland_get_failed", detail=str(exc))
    if not response.is_success:
        return _err("bland_get_failed", status_code=response.status_code)
    return {"ok": True, "call": response.json()}


def transcript_from_call(call: dict) -> list[dict]:
    events: list[dict] = []
    rows = call.get("transcripts") or call.get("concatenated_transcript") or []
    if isinstance(rows, str):
        for line in rows.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                speaker, text = line.split(":", 1)
                low = speaker.lower()
                if any(k in low for k in ("agent", "assistant", "ai", "bot", "cashe", caller_name().lower())):
                    role = "caller"
                else:
                    role = "counterparty"
                events.append({"ts": "", "speaker": role, "text": text.strip()})
            else:
                events.append({"ts": "", "speaker": "unknown", "text": line})
        return events
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or item.get("message") or "").strip()
        if not text:
            continue
        user = (item.get("user") or item.get("speaker") or "").lower()
        speaker = "caller" if user in {"assistant", "agent", "ai", "bot"} else "counterparty"
        events.append(
            {
                "ts": str(item.get("created_at") or item.get("createdAt") or ""),
                "speaker": speaker,
                "text": text,
            }
        )
    return events


def place_and_wait(
    to_number: str,
    objective: str | None = None,
    allowed_questions: list[str] | None = None,
    timeout_s: float = POLL_TIMEOUT_S,
) -> dict:
    placed = place_call(to_number, objective, allowed_questions)
    if placed.get("error"):
        return placed
    call_id = placed.get("id")
    if not call_id:
        return _err("bland_missing_call_id", body=placed)
    deadline = time.time() + timeout_s
    last: dict = placed.get("call") or {}
    while time.time() < deadline:
        fetched = get_call(call_id)
        if fetched.get("error"):
            time.sleep(POLL_INTERVAL_S)
            continue
        last = fetched.get("call") or {}
        status = (last.get("status") or last.get("queue_status") or "").lower()
        if status in TERMINAL_STATUSES:
            break
        time.sleep(POLL_INTERVAL_S)
    return {
        "ok": True,
        "id": call_id,
        "status": last.get("status"),
        "call": last,
        "transcript": transcript_from_call(last),
        "provider": "bland",
    }
