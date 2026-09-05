"""Outbound Cashe collections call via Vapi (AI = collections caller).

No ngrok. Returns dicts — never sys.exit — so the investigation tool can fall through.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

from cashe.voice.realtime_common import (
    collections_first_message,
    collections_instructions,
    caller_name,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=True)

API = "https://api.vapi.ai"
TERMINAL_STATUSES = {"ended", "completed", "failed", "error", "canceled", "cancelled"}
POLL_TIMEOUT_S = 90.0
POLL_INTERVAL_S = 2.5


def _headers() -> dict[str, str] | dict:
    key = os.getenv("VAPI_API_KEY", "").strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _err(message: str, **extra) -> dict:
    return {"error": message, **extra}


def list_phone_numbers() -> list[dict] | dict:
    headers = _headers()
    if not headers:
        return _err("missing_vapi_api_key")
    try:
        response = httpx.get(f"{API}/phone-number", headers=headers, timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return _err("vapi_phone_list_failed", detail=str(exc))
    data = response.json()
    if isinstance(data, list):
        return data
    return data.get("results") or data.get("data") or []


def ensure_openai_credential() -> dict:
    """BYOK: bill LLM/TTS to our OpenAI key (not Vapi pass-through)."""
    headers = _headers()
    if not headers:
        return _err("missing_vapi_api_key")
    oa = os.getenv("OPENAI_API_KEY", "").strip()
    if not oa:
        return {"ok": True, "note": "OPENAI_API_KEY missing — Vapi may bill pass-through"}

    try:
        response = httpx.get(f"{API}/credential", headers=headers, timeout=30)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return _err("vapi_credential_list_failed", detail=str(exc))
    raw = response.json()
    creds = raw if isinstance(raw, list) else []
    if any(c.get("provider") == "openai" for c in creds):
        return {"ok": True, "note": "openai_credential_present"}

    try:
        created = httpx.post(
            f"{API}/credential",
            headers=headers,
            json={"provider": "openai", "apiKey": oa},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        return _err("vapi_credential_create_failed", detail=str(exc))
    if not created.is_success:
        return _err("vapi_credential_create_failed", status_code=created.status_code)
    return {"ok": True, "id": created.json().get("id")}


def ensure_phone_number_id() -> dict:
    existing = os.getenv("VAPI_PHONE_NUMBER_ID", "").strip()
    if existing:
        return {"ok": True, "id": existing}

    numbers = list_phone_numbers()
    if isinstance(numbers, dict) and numbers.get("error"):
        return numbers
    if numbers:
        pid = numbers[0].get("id")
        return {"ok": True, "id": pid, "number": numbers[0].get("number")}

    headers = _headers()
    area = os.getenv("VAPI_AREA_CODE", "415").strip() or "415"
    try:
        response = httpx.post(
            f"{API}/phone-number",
            headers=headers,
            json={"provider": "vapi", "numberDesiredAreaCode": area},
            timeout=60,
        )
    except httpx.HTTPError as exc:
        return _err("vapi_phone_create_failed", detail=str(exc))
    if not response.is_success:
        return _err(
            "vapi_phone_create_failed",
            status_code=response.status_code,
            hint="Create a free Vapi number in the dashboard and set VAPI_PHONE_NUMBER_ID",
        )
    body = response.json()
    return {"ok": True, "id": body.get("id"), "number": body.get("number")}


def build_assistant(objective: str | None = None, allowed_questions: list[str] | None = None) -> dict:
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    return {
        "name": "Cashe Collections Caller",
        "firstMessage": collections_first_message(objective),
        "model": {
            "provider": "openai",
            "model": model_name,
            "temperature": 0.4,
            "messages": [
                {
                    "role": "system",
                    "content": collections_instructions(objective, allowed_questions),
                }
            ],
        },
        "voice": {
            "provider": "openai",
            "voiceId": os.getenv("VAPI_VOICE_ID", "alloy"),
        },
    }


def _normalize_e164(number: str) -> str:
    to_number = (number or "").strip()
    if not to_number:
        return ""
    if not to_number.startswith("+"):
        to_number = "+1" + "".join(c for c in to_number if c.isdigit())[-10:]
    return to_number


def place_call(
    to_number: str,
    objective: str | None = None,
    allowed_questions: list[str] | None = None,
) -> dict:
    headers = _headers()
    if not headers:
        return _err("missing_vapi_api_key")
    dest = _normalize_e164(to_number)
    if not dest:
        return _err("missing_destination")

    cred = ensure_openai_credential()
    if cred.get("error"):
        return cred
    phone = ensure_phone_number_id()
    if phone.get("error"):
        return phone
    phone_number_id = phone.get("id")
    payload = {
        "assistant": build_assistant(objective, allowed_questions),
        "phoneNumberId": phone_number_id,
        "customer": {"number": dest},
    }
    try:
        response = httpx.post(f"{API}/call", headers=headers, json=payload, timeout=60)
    except httpx.HTTPError as exc:
        return _err("vapi_call_failed", detail=str(exc))
    if not response.is_success:
        return _err("vapi_call_failed", status_code=response.status_code, body=response.text[:500])
    body = response.json()
    return {"ok": True, "call": body, "id": body.get("id"), "status": body.get("status")}


def get_call(call_id: str) -> dict:
    headers = _headers()
    if not headers:
        return _err("missing_vapi_api_key")
    try:
        response = httpx.get(f"{API}/call/{call_id}", headers=headers, timeout=30)
    except httpx.HTTPError as exc:
        return _err("vapi_get_failed", detail=str(exc))
    if not response.is_success:
        return _err("vapi_get_failed", status_code=response.status_code)
    return {"ok": True, "call": response.json()}


def messages_to_transcript(messages: list) -> list[dict]:
    events: list[dict] = []
    for item in messages or []:
        if not isinstance(item, dict):
            continue
        role = (item.get("role") or "").lower()
        text = (item.get("message") or item.get("content") or item.get("text") or "").strip()
        if not text or role in {"system", "tool", "function"}:
            continue
        speaker = "caller" if role in {"bot", "assistant"} else "counterparty"
        ts = item.get("time") or item.get("timestamp") or item.get("createdAt") or ""
        events.append({"ts": str(ts), "speaker": speaker, "text": text})
    return events


def transcript_from_call(call: dict) -> list[dict]:
    messages = call.get("messages") or []
    events = messages_to_transcript(messages)
    if events:
        return events
    raw = (call.get("transcript") or "").strip()
    if not raw:
        return []
    events = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            speaker, text = line.split(":", 1)
            low = speaker.lower()
            role = "caller" if any(k in low for k in ("ai", "bot", "assistant", "cashe", caller_name().lower())) else "counterparty"
            events.append({"ts": "", "speaker": role, "text": text.strip()})
        else:
            events.append({"ts": "", "speaker": "unknown", "text": line})
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
        return _err("vapi_missing_call_id", body=placed)
    deadline = time.time() + timeout_s
    last: dict = placed.get("call") or {}
    while time.time() < deadline:
        fetched = get_call(call_id)
        if fetched.get("error"):
            time.sleep(POLL_INTERVAL_S)
            continue
        last = fetched.get("call") or {}
        status = (last.get("status") or "").lower()
        if status in TERMINAL_STATUSES:
            break
        time.sleep(POLL_INTERVAL_S)
    return {
        "ok": True,
        "id": call_id,
        "status": last.get("status"),
        "call": last,
        "transcript": transcript_from_call(last),
        "provider": "vapi",
    }
