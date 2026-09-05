"""Place an outbound voice call and return the full transcript.

The tool supplies a purpose (objective). This module does not know HarborLine,
invoices, or any other counterparty script. It dials, waits, and hands the
transcript back to the voice subagent.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from cashe.config import settings
from cashe.sources import harborline
from cashe.voice import bland_call, vapi_call

LIVE_TIMEOUT_S = 90.0
LOCAL_HEALTH_TIMEOUT_S = 2.0


def live_destination(source_phone: str = "") -> str:
    raw = (
        settings.voice_to_number
        or settings.harborline_phone
        or source_phone
        or ""
    ).strip()
    if not raw:
        return ""
    if not raw.startswith("+"):
        digits = "".join(c for c in raw if c.isdigit())[-10:]
        if len(digits) == 10:
            raw = "+1" + digits
    return raw


def local_server_reachable(base: str, timeout: float = LOCAL_HEALTH_TIMEOUT_S) -> bool:
    url = (base or "").rstrip("/")
    if not url:
        return False
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError:
        return False
    return response.is_success


def build_voice_payload(
    *,
    purpose: str,
    allowed_questions: list[str],
    turn_budget: int,
    transcript: list[dict],
    provider: str,
    mocked: bool,
    live: bool,
    note: str,
    source_id: str = "",
    call_id: str = "",
) -> dict:
    return {
        "mocked": mocked,
        "live": live,
        "agent": "voice",
        "source_id": source_id,
        "purpose": purpose,
        "objective": purpose,
        "allowed_questions": allowed_questions,
        "turn_budget": turn_budget,
        "turns_used": len(transcript),
        "transcript": transcript,
        "authority": "COMMUNICATION",
        "confidence": "provisional",
        "requires_documentary_corroboration": True,
        "provider": provider,
        "call_id": call_id,
        "note": note,
    }


def _poll_local_transcript(base: str, timeout_s: float = LIVE_TIMEOUT_S) -> list[dict] | None:
    deadline = time.time() + timeout_s
    url = base.rstrip("/") + "/transcript"
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            data = response.json()
        except (httpx.HTTPError, ValueError):
            time.sleep(2.0)
            continue
        if data.get("status") == "complete" and data.get("transcript"):
            return data["transcript"]
        time.sleep(2.0)
    return None


def _try_local_bridge(
    base: str,
    dest: str,
    provider: str,
    purpose: str,
    allowed_questions: list[str],
    turn_budget: int,
    source_id: str,
) -> dict | None:
    if not local_server_reachable(base):
        return None
    try:
        response = httpx.post(
            f"{base.rstrip('/')}/call",
            json={"to": dest, "objective": purpose, "allowed_questions": allowed_questions},
            timeout=15.0,
        )
    except httpx.HTTPError:
        return None
    if not response.is_success:
        return None
    transcript = _poll_local_transcript(base)
    if not transcript:
        return None
    return build_voice_payload(
        purpose=purpose,
        allowed_questions=allowed_questions,
        turn_budget=turn_budget,
        transcript=transcript,
        provider=provider,
        mocked=False,
        live=True,
        note=f"Live PSTN via local {provider} realtime server.",
        source_id=source_id,
    )


def _from_live_provider(
    result: dict,
    provider: str,
    purpose: str,
    allowed_questions: list[str],
    turn_budget: int,
    source_id: str,
) -> dict | None:
    if result.get("error"):
        return None
    transcript = result.get("transcript") or []
    if not transcript:
        return None
    return build_voice_payload(
        purpose=purpose,
        allowed_questions=allowed_questions,
        turn_budget=turn_budget,
        transcript=transcript,
        provider=provider,
        mocked=False,
        live=True,
        note=f"Live outbound call via {provider}.",
        source_id=source_id,
        call_id=str(result.get("id") or ""),
    )


def place_voice_call(
    purpose: str,
    allowed_questions: list[str] | None = None,
    turn_budget: int = 8,
    source_phone: str = "",
    source_id: str = "",
    **_: Any,
) -> dict:
    dest = live_destination(source_phone)
    questions = list(allowed_questions or [])

    if settings.vapi_api_key and dest:
        live = _from_live_provider(
            vapi_call.place_and_wait(dest, purpose, questions),
            "vapi",
            purpose,
            questions,
            turn_budget,
            source_id,
        )
        if live:
            return live

    if settings.bland_api_key and dest:
        live = _from_live_provider(
            bland_call.place_and_wait(dest, purpose, questions),
            "bland",
            purpose,
            questions,
            turn_budget,
            source_id,
        )
        if live:
            return live

    if dest:
        telnyx = _try_local_bridge(
            settings.local_server, dest, "telnyx", purpose, questions, turn_budget, source_id
        )
        if telnyx:
            return telnyx
        twilio = _try_local_bridge(
            settings.local_server_twilio, dest, "twilio", purpose, questions, turn_budget, source_id
        )
        if twilio:
            return twilio

    fallback = harborline.mock_voice_call(purpose, questions, turn_budget)
    fallback["source_id"] = source_id or fallback.get("source_id")
    fallback["purpose"] = purpose
    return fallback


# Older import name used by the investigation tool.
place_harborline_call = place_voice_call
