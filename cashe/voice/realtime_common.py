"""Shared outbound-caller prompt + transcript helpers for Telnyx/Twilio Realtime bridges.

Adapted from the pizza-ordering voice agent: same telephony tools (wait / press_digit /
end_call), DTMF, hold/IVR helpers, and transcript logging. The call purpose is
supplied by place_voice_call — nothing about a specific counterparty is hardcoded.
"""

from __future__ import annotations

import base64
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent.parent
TRANSCRIPT_DIR = REPO_ROOT / "data" / "voice_transcripts"
TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

# Hangup unlock: short thanks/bye after the desk has answered.
GOODBYE_PHRASE_RE = re.compile(
    r"\bthanks?\b|\bthank you\b|\bbye\b|\bgoodbye\b|"
    r"\bappreciate (?:it|your time)\b|"
    r"\bthat's all i needed\b|"
    r"\bhave a (?:good|great) (?:day|one)\b",
    re.I,
)

# Back-compat alias used by older pizza-agent call sites.
CANCEL_PHRASE_RE = GOODBYE_PHRASE_RE

ETA_RE = re.compile(
    r"\b(\d{1,3})\s*(?:to|-|–)\s*(\d{1,3})\s*minutes?\b"
    r"|\b(?:about|around|within|in)\s+(\d{1,3})\s*minutes?\b"
    r"|\b(\d{1,3})\s*minutes?\b",
    re.I,
)

HOLD_FILLER_RE = re.compile(
    r"please hold|one moment|just a (?:moment|sec|second|minute)|"
    r"transfer(?:ring)?|privacy policy|calls may be recorded|"
    r"menu options have changed|thank you for calling|"
    r"for quality and training|visit (?:us at )?www|"
    r"please stay on the line|quick survey",
    re.I,
)

HUMAN_QUESTION_RE = re.compile(
    r"\?"
    r"|\b(?:can|may|could)\s+i\s+(?:have|get|ask)"
    r"|\b(?:what(?:'s| is)|where|when|who|how)\b"
    r"|\b(?:your|the)\s+(?:name|company|invoice|account|phone|number)"
    r"|\bhow can i (?:help|assist)\b"
    r"|\bis that correct\b"
    r"|\bare you still there\b"
    r"|\bhello\b.{0,20}\b(?:how can|can i|name|company)",
    re.I,
)

WAIT_AFTER_INSTRUCTIONS = (
    "Check the latest audio. "
    "If a REAL PERSON asked you something, answer that question NOW as the "
    "caller — do NOT call wait. Only if you are still on hold music / transfer "
    "silence with no question, call wait once more (15–25s) and stay mute. "
    "Never act as the other party's staff."
)

ANSWER_NOW_INSTRUCTIONS = (
    "A real person just spoke to you. Answer ONLY their latest question "
    "as the CALLER in one short sentence. Do NOT call wait. "
    "Never act as the other party's staff."
)

WRAP_UP_INSTRUCTIONS = (
    "You have an answer to the purpose of this call. As the caller, "
    "say a short thanks/bye, then call end_call(). "
    "Never act as the other party's staff. Do not invent facts."
)

# Pizza-agent name kept so Telnyx/Twilio bridges can import it unchanged.
ORDER_DONE_INSTRUCTIONS = WRAP_UP_INSTRUCTIONS

END_CALL_BLOCKED_INSTRUCTIONS = (
    "Stay as the caller. Keep going until the purpose of the call is answered "
    "(or they clearly cannot answer). Then say a short thanks/bye and "
    "call end_call(). Never act as the other party's staff. Do not invent facts."
)

# ITU DTMF low/high tone pairs (Hz)
_DTMF_FREQS: dict[str, tuple[float, float]] = {
    "1": (697, 1209),
    "2": (697, 1336),
    "3": (697, 1477),
    "A": (697, 1633),
    "4": (770, 1209),
    "5": (770, 1336),
    "6": (770, 1477),
    "B": (770, 1633),
    "7": (852, 1209),
    "8": (852, 1336),
    "9": (852, 1477),
    "C": (852, 1633),
    "*": (941, 1209),
    "0": (941, 1336),
    "#": (941, 1477),
    "D": (941, 1633),
}

LAST_CALL: dict = {"status": "idle", "transcript": []}


def caller_name() -> str:
    return os.getenv("CUSTOMER_NAME", "Alex").strip() or "Alex"


def first_message(purpose: str = "") -> str:
    name = caller_name()
    purpose = (purpose or "").strip()
    if purpose:
        return f"Hi, this is {name} calling. {purpose}"
    return f"Hi, this is {name} calling."


def caller_instructions(
    purpose: str = "",
    allowed_questions: list[str] | None = None,
) -> str:
    name = caller_name()
    phone = os.getenv("CUSTOMER_PHONE", "").strip() or "the number on file"
    purpose = (purpose or "").strip()
    questions = [q for q in (allowed_questions or []) if str(q).strip()]
    question_block = "\n".join(f"- {q}" for q in questions) or "- Stay inside the purpose above."
    return f"""
You are {name}, a HUMAN CALLER on a live phone call. You are never the other party's staff.
If you feel like taking their side of the conversation — STOP. You placed this call.

ROLE LOCK
- You are the caller. They answer.
- Never say: "How can I help", "I'm here to assist", "Let me look that up for you".
- After hold or transfer you are STILL {name} the caller.
- Never invent confirmation numbers, payment dates, or documents they did not say.

SPEECH
- Let them finish. Answer ONLY the question they asked (one short sentence).
- Name → {name}. Callback phone → {phone}.
- Do not talk over greetings or hold music.
- No markdown, no lists, no stage directions.

PURPOSE OF THIS CALL
{purpose}

ALLOWED QUESTIONS (stay inside this list)
{question_block}

TOOLS
- press_digit(digit): IVR menus only (e.g. English = 1, operator = 0). Do NOT just say the digit.
- wait(seconds): ONLY for hold music / transfer silence. Never call wait while a person is asking you questions.
- end_call(): Hang up ONLY after the purpose is answered (or they cannot provide more) and you said a short thanks/bye.

FLOW
1) Stay quiet until they ask something or finish IVR prompts. Use press_digit for menus.
2) Identify yourself as {name} and pursue the purpose of the call.
3) Ask only the allowed questions. Do not invent facts they did not say.
4) When the purpose is answered (or they clearly cannot), say a short thanks/bye.
5) Immediately call end_call().
""".strip()


# Names used by the Telnyx/Twilio/Vapi/Bland adapters.
collections_first_message = first_message
collections_instructions = caller_instructions


def openai_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "name": "wait",
            "description": (
                "Stay completely silent on hold/transfer/music. Do not speak. "
                "Use only when nobody is asking you a question. May call repeatedly on long holds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Seconds to wait silently (1–30).",
                    }
                },
                "required": ["seconds"],
            },
        },
        {
            "type": "function",
            "name": "press_digit",
            "description": (
                "Send a real phone keypad digit (DTMF) for IVR menus, "
                "e.g. press 1 for English or press 0 for an operator."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "digit": {
                        "type": "string",
                        "description": "One digit: 0-9, *, or #",
                    }
                },
                "required": ["digit"],
            },
        },
        {
            "type": "function",
            "name": "end_call",
            "description": (
                "Hang up. Only after you thanked them and said goodbye "
                "once you have the desk's answer (or they cannot provide more)."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    ]


def is_hold_filler(text: str) -> bool:
    return bool(HOLD_FILLER_RE.search(text or ""))


def is_human_question(text: str) -> bool:
    t = (text or "").strip()
    if not t or is_hold_filler(t):
        return False
    return bool(HUMAN_QUESTION_RE.search(t))


def looks_like_eta(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if is_hold_filler(t) and "minute" not in t.lower():
        return False
    m = ETA_RE.search(t)
    if not m:
        return False
    low = t.lower()
    if any(
        k in low
        for k in (
            "minute",
            "delivery",
            "receive",
            "arrive",
            "ready in",
            "about",
            "within",
        )
    ):
        return True
    return "minute" in low


def looks_like_status_answer(text: str) -> bool:
    t = (text or "").strip()
    if not t or is_hold_filler(t):
        return False
    return len(t.split()) >= 6


def is_english_ivr(text: str) -> bool:
    low = (text or "").lower()
    return "press 1" in low and "english" in low


def _linear16_to_ulaw(sample: int) -> int:
    """G.711 μ-law encode one signed 16-bit PCM sample (no audioop; Py3.13+)."""
    BIAS = 0x84
    CLIP = 32635
    sign = 0x80 if sample < 0 else 0x00
    if sample < 0:
        sample = -sample
    if sample > CLIP:
        sample = CLIP
    sample += BIAS
    exponent = 7
    mask = 0x4000
    while exponent > 0 and not (sample & mask):
        mask >>= 1
        exponent -= 1
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def pcmu_dtmf_frames(
    digit: str,
    *,
    duration_ms: int = 240,
    gap_ms: int = 100,
    frame_ms: int = 20,
    sample_rate: int = 8000,
) -> list[str]:
    """Return base64 PCMU frames for one DTMF digit (+ short silence gap)."""
    key = (digit or "1").strip()[:1].upper()
    if key not in _DTMF_FREQS:
        key = "1"
    f1, f2 = _DTMF_FREQS[key]
    tone_n = max(1, int(sample_rate * duration_ms / 1000))
    gap_n = max(0, int(sample_rate * gap_ms / 1000))
    samples: list[int] = []
    for i in range(tone_n):
        t = i / sample_rate
        val = 0.35 * math.sin(2 * math.pi * f1 * t) + 0.35 * math.sin(
            2 * math.pi * f2 * t
        )
        samples.append(int(max(-32767, min(32767, val * 32767))))
    samples.extend([0] * gap_n)
    ulaw = bytes(_linear16_to_ulaw(s) for s in samples)
    frame_bytes = max(1, int(sample_rate * frame_ms / 1000))
    out: list[str] = []
    for off in range(0, len(ulaw), frame_bytes):
        chunk = ulaw[off : off + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk = chunk + bytes([0xFF]) * (frame_bytes - len(chunk))
        out.append(base64.b64encode(chunk).decode("ascii"))
    return out


def set_last_call(payload: dict) -> None:
    LAST_CALL.clear()
    LAST_CALL.update(payload)


def get_last_call() -> dict:
    return dict(LAST_CALL)


class TranscriptLog:
    def __init__(self, to_number: str, from_number: str = "") -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe = "".join(c for c in to_number if c.isdigit()) or "unknown"
        self.path = TRANSCRIPT_DIR / f"call_{safe}_{stamp}.md"
        self.events: list[dict] = []
        self.lines: list[str] = [
            f"# Call transcript — {to_number}",
            f"- Started (UTC): {datetime.now(timezone.utc).isoformat()}",
            f"- From: {from_number}",
            "",
            "## Dialogue",
            "",
        ]
        self.path.write_text("\n".join(self.lines) + "\n")
        print(f"Transcript → {self.path}", flush=True)
        set_last_call({"status": "in_progress", "transcript": [], "path": str(self.path)})

    def add(self, speaker: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        line = f"**{speaker}:** {text}"
        self.lines.append(line)
        print(f"TRANSCRIPT {speaker}: {text}", flush=True)
        with self.path.open("a") as f:
            f.write(line + "\n\n")
        role = {
            "Cashe collections": "caller",
            "caller": "caller",
            "HarborLine": "counterparty",
            "counterparty": "counterparty",
            "system": "system",
        }.get(speaker, speaker)
        self.events.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "speaker": role,
                "text": text,
            }
        )
        set_last_call(
            {
                "status": "in_progress",
                "transcript": [e for e in self.events if e["speaker"] != "system"],
                "path": str(self.path),
            }
        )

    def dialogue(self) -> list[dict]:
        return [e for e in self.events if e["speaker"] != "system"]

    def close(self, note: str = "") -> None:
        with self.path.open("a") as f:
            f.write(
                f"\n## End\n- Ended (UTC): {datetime.now(timezone.utc).isoformat()}\n"
            )
            if note:
                f.write(f"- Note: {note}\n")
        print(f"Transcript saved: {self.path}", flush=True)
        set_last_call(
            {
                "status": "complete",
                "transcript": self.dialogue(),
                "path": str(self.path),
                "note": note,
            }
        )
