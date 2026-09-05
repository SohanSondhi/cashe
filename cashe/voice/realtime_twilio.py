"""
Outbound Cashe collections call: Twilio Voice + Media Streams + OpenAI Realtime (PCMU).

Run (separate from Telnyx — use its own port / ngrok if needed):
  uvicorn cashe.voice.realtime_twilio:app --host 0.0.0.0 --port 8081
  # PUBLIC_BASE_URL must point at this process (ngrok http 8081)
  python -m cashe.voice.call_twilio
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, VoiceResponse

from cashe.voice.realtime_common import (
    ANSWER_NOW_INSTRUCTIONS,
    END_CALL_BLOCKED_INSTRUCTIONS,
    GOODBYE_PHRASE_RE,
    WAIT_AFTER_INSTRUCTIONS,
    TranscriptLog,
    caller_name,
    collections_instructions,
    greet_instructions,
    inbound_audio_payload,
    get_last_call,
    is_english_ivr,
    is_hold_filler,
    is_human_question,
    looks_like_status_answer,
    openai_tools,
    pcmu_dtmf_frames,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env", override=False)

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

OPENAI_REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1")
OPENAI_VOICE = os.getenv("OPENAI_VOICE", "marin")
OPENAI_REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={OPENAI_REALTIME_MODEL}"

app = FastAPI(title="Cashe collections Twilio + OpenAI Realtime")

_pending_to: str | None = None
_pending_objective: str | None = None
_pending_questions: list[str] | None = None
_active_call_sid: str | None = None


class CallRequest(BaseModel):
    to: str
    objective: str | None = None
    allowed_questions: list[str] | None = None


def _demo_destination() -> str:
    return (
        os.getenv("VOICE_TO_NUMBER")
        or os.getenv("HARBORLINE_PHONE")
        or ""
    ).strip()


def _require_env() -> None:
    missing = [
        name
        for name, val in [
            ("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID),
            ("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN),
            ("TWILIO_FROM_NUMBER", TWILIO_FROM_NUMBER),
            ("OPENAI_API_KEY", OPENAI_API_KEY),
            ("PUBLIC_BASE_URL", PUBLIC_BASE_URL),
        ]
        if not val
    ]
    if missing:
        raise HTTPException(500, f"Missing env: {', '.join(missing)}")


def public_ws_url(path: str) -> str:
    if PUBLIC_BASE_URL.startswith("https://"):
        return "wss://" + PUBLIC_BASE_URL.removeprefix("https://") + path
    if PUBLIC_BASE_URL.startswith("http://"):
        return "ws://" + PUBLIC_BASE_URL.removeprefix("http://") + path
    raise RuntimeError("PUBLIC_BASE_URL must start with http:// or https://")


def twilio_client() -> Client:
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "provider": "twilio",
        "public_base_url": PUBLIC_BASE_URL or None,
        "from": TWILIO_FROM_NUMBER or None,
        "destination": _demo_destination() or None,
        "model": OPENAI_REALTIME_MODEL,
        "voice": OPENAI_VOICE,
        "mode": "cashe-voice",
    }


@app.get("/transcript")
async def transcript():
    return get_last_call()


@app.post("/call")
async def create_call(call: CallRequest):
    global _pending_to, _pending_objective, _pending_questions, _active_call_sid
    _require_env()
    to = call.to.strip()
    if not to.startswith("+"):
        raise HTTPException(400, "Use E.164 (e.g. +14155550100)")
    _pending_to = to
    _pending_objective = call.objective
    _pending_questions = call.allowed_questions

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Connect><Stream url="{public_ws_url("/media-stream")}" /></Connect></Response>'
    )
    print(f"Dialing {to} from {TWILIO_FROM_NUMBER} …")
    try:
        created = twilio_client().calls.create(
            from_=TWILIO_FROM_NUMBER,
            to=to,
            twiml=twiml,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc
    _active_call_sid = created.sid
    return {"sid": created.sid, "status": created.status, "to": to, "from": TWILIO_FROM_NUMBER}


@app.post("/twilio/play-digit")
async def play_digit(digit: str = "1"):
    """TwiML: play DTMF then reconnect Media Stream (used by press_digit)."""
    d = digit.strip()[:1] if digit else "1"
    if d not in "0123456789*#":
        d = "1"
    resp = VoiceResponse()
    resp.play(digits=d)
    connect = Connect()
    connect.stream(url=public_ws_url("/media-stream"))
    resp.append(connect)
    return Response(content=str(resp), media_type="application/xml")


async def send_openai_session_update(openai_ws) -> None:
    event = {
        "type": "session.update",
        "session": {
            "type": "realtime",
            "model": OPENAI_REALTIME_MODEL,
            "instructions": collections_instructions(_pending_objective, _pending_questions),
            "output_modalities": ["audio"],
            "tool_choice": "auto",
            "tools": openai_tools(),
            "audio": {
                "input": {
                    "format": {"type": "audio/pcmu"},
                    "turn_detection": {
                        "type": "semantic_vad",
                        "eagerness": "low",
                    },
                    "transcription": {"model": "gpt-4o-mini-transcribe"},
                },
                "output": {
                    "format": {"type": "audio/pcmu"},
                    "voice": OPENAI_VOICE,
                },
            },
        },
    }
    await openai_ws.send(json.dumps(event))


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    global _active_call_sid
    await websocket.accept()
    print("Twilio media WebSocket accepted", flush=True)

    if not OPENAI_API_KEY:
        await websocket.close(code=1011)
        return

    log = TranscriptLog(_pending_to or "unknown", TWILIO_FROM_NUMBER)
    name = caller_name()
    bg_tasks: set[asyncio.Task] = set()

    async with websockets.connect(
        OPENAI_REALTIME_URL,
        additional_headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
    ) as openai_ws:
        await send_openai_session_update(openai_ws)
        session_ready = asyncio.Event()
        hanging_up = False
        goodbye_said = False
        status_heard = False
        dtmf_1_sent = False
        auto_ivr_started = False
        on_hold = False
        response_busy = False
        stream_sid: str | None = None
        call_sid: str | None = _active_call_sid
        assistant_buf: list[str] = []
        active_wait_task: asyncio.Task | None = None

        def track(task: asyncio.Task) -> asyncio.Task:
            bg_tasks.add(task)
            task.add_done_callback(bg_tasks.discard)
            return task

        async def tool_output(call_id: str, payload: dict) -> None:
            await openai_ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(payload),
                        },
                    }
                )
            )

        async def create_response(instructions: str) -> None:
            nonlocal response_busy
            if response_busy:
                try:
                    await openai_ws.send(json.dumps({"type": "response.cancel"}))
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(0.05)
            response_busy = True
            await openai_ws.send(
                json.dumps(
                    {
                        "type": "response.create",
                        "response": {"instructions": instructions},
                    }
                )
            )

        def cancel_active_wait() -> None:
            nonlocal active_wait_task, on_hold
            if active_wait_task and not active_wait_task.done():
                active_wait_task.cancel()
            active_wait_task = None
            on_hold = False

        async def hangup() -> None:
            nonlocal hanging_up
            hanging_up = True
            cancel_active_wait()
            for task in list(bg_tasks):
                task.cancel()
            sid = call_sid or _active_call_sid
            if not sid:
                return
            try:
                await asyncio.to_thread(
                    lambda: twilio_client().calls(sid).update(status="completed")
                )
                print(f"Hung up {sid}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"Hangup failed: {exc}", flush=True)

        async def send_dtmf_digit(digit: str) -> None:
            """Inject PCMU DTMF into the live Media Stream (no reconnect)."""
            nonlocal stream_sid
            if not stream_sid:
                sid = call_sid or _active_call_sid
                if not sid:
                    return
                url = f"{PUBLIC_BASE_URL}/twilio/play-digit?digit={digit}"
                try:
                    await asyncio.to_thread(
                        lambda: twilio_client().calls(sid).update(url=url, method="POST")
                    )
                    print(f"DTMF via TwiML fallback: {digit}", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"DTMF failed: {exc}", flush=True)
                return

            frames = pcmu_dtmf_frames(digit)
            try:
                for payload in frames:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": payload},
                            }
                        )
                    )
                    await asyncio.sleep(0.02)
                print(f"DTMF in-band: {digit} ({len(frames)} frames)", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"DTMF in-band failed: {exc}", flush=True)

        async def auto_ivr_digits() -> None:
            digits = os.getenv("AUTO_DTMF_DIGITS", "").strip()
            if not digits:
                return
            delay = float(os.getenv("AUTO_DTMF_DELAY_S", "4.0"))
            try:
                await asyncio.sleep(max(0.5, delay))
                if hanging_up or not stream_sid:
                    return
                for ch in digits:
                    if hanging_up:
                        return
                    if ch not in "0123456789*#":
                        continue
                    log.add("system", f"auto DTMF {ch} (startup IVR)")
                    print(f"Auto DTMF {ch}", flush=True)
                    await send_dtmf_digit(ch)
                    await asyncio.sleep(1.4)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                print(f"auto_ivr_digits error: {exc}", flush=True)

        async def finish_wait(tool_call_id: str, seconds: float) -> None:
            nonlocal on_hold, active_wait_task
            try:
                await asyncio.sleep(seconds)
                if hanging_up:
                    return
                on_hold = False
                await tool_output(
                    tool_call_id,
                    {
                        "ok": True,
                        "waited_seconds": seconds,
                        "reminder": (
                            f"You are still {name} from Cashe collections. Stay silent unless they "
                            "asked you a question. Never speak as the other party's staff."
                        ),
                    },
                )
                await create_response(WAIT_AFTER_INSTRUCTIONS)
            except asyncio.CancelledError:
                try:
                    await tool_output(
                        tool_call_id,
                        {
                            "ok": True,
                            "waited_seconds": 0,
                            "cancelled": True,
                            "reminder": f"Wait cancelled — listen/answer as {name} from Cashe collections.",
                        },
                    )
                except Exception:  # noqa: BLE001
                    pass
                raise
            except Exception as exc:  # noqa: BLE001
                print(f"finish_wait error: {exc}", flush=True)
            finally:
                if active_wait_task is asyncio.current_task():
                    active_wait_task = None
                on_hold = False

        async def handle_tool(tool_name: str, tool_call_id: str, arguments: str) -> None:
            nonlocal hanging_up, goodbye_said, on_hold, active_wait_task
            try:
                args = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if tool_name == "wait":
                seconds = float(args.get("seconds") or 8)
                seconds = max(1.0, min(seconds, 30.0))
                log.add("system", f"wait({seconds}s)")
                cancel_active_wait()
                on_hold = True
                active_wait_task = track(
                    asyncio.create_task(finish_wait(tool_call_id, seconds))
                )
            elif tool_name == "press_digit":
                digit = str(args.get("digit") or "1").strip()[:1]
                if digit not in "0123456789*#":
                    digit = "1"
                log.add("system", f"press_digit({digit})")
                await send_dtmf_digit(digit)
                await tool_output(tool_call_id, {"ok": True, "digit": digit})
                await create_response(
                    f"Digit sent. Stay silent and listen for the next IVR prompt "
                    f"or a person. You are still {name} from Cashe collections."
                )
            elif tool_name == "end_call":
                if not goodbye_said:
                    log.add("system", "end_call blocked — goodbye not said yet")
                    await tool_output(
                        tool_call_id,
                        {
                            "ok": False,
                            "error": (
                                "Say a short thanks/bye first, then call end_call."
                            ),
                        },
                    )
                    await create_response(END_CALL_BLOCKED_INSTRUCTIONS)
                    return
                log.add("system", "end_call()")
                await tool_output(tool_call_id, {"ok": True, "hanging_up": True})
                await asyncio.sleep(0.4)
                await hangup()
            else:
                await tool_output(tool_call_id, {"ok": False, "error": "unknown tool"})

        async def auto_hangup_after_goodbye() -> None:
            await asyncio.sleep(1.6)
            if not hanging_up and goodbye_said:
                log.add("system", "auto hangup after goodbye")
                await hangup()

        async def twilio_to_openai():
            global _active_call_sid
            nonlocal stream_sid, call_sid, auto_ivr_started
            try:
                while True:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    event = data.get("event")

                    if event == "start":
                        start = data.get("start") or {}
                        stream_sid = start.get("streamSid") or stream_sid
                        call_sid = start.get("callSid") or call_sid
                        if call_sid:
                            _active_call_sid = call_sid
                        print("Twilio stream started", stream_sid, call_sid, flush=True)
                        await session_ready.wait()
                        log.add("system", "greeting")
                        await create_response(greet_instructions())
                        if not auto_ivr_started:
                            auto_ivr_started = True
                            track(asyncio.create_task(auto_ivr_digits()))
                    elif event == "media":
                        if hanging_up:
                            continue
                        payload = inbound_audio_payload(data)
                        if not payload:
                            continue
                        await openai_ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": payload,
                                }
                            )
                        )
                    elif event == "stop":
                        print("Twilio stream stopped", flush=True)
                        break
            except WebSocketDisconnect:
                print("Twilio WebSocket disconnected", flush=True)

        async def openai_to_twilio():
            nonlocal hanging_up, goodbye_said, dtmf_1_sent, response_busy, status_heard
            async for message in openai_ws:
                if hanging_up:
                    break
                data = json.loads(message)
                event_type = data.get("type")

                if event_type == "session.created":
                    print("OpenAI session created", flush=True)
                elif event_type == "session.updated":
                    session_ready.set()
                    print("OpenAI session updated", flush=True)
                elif event_type == "input_audio_buffer.speech_started":
                    if hanging_up or on_hold:
                        continue
                    await openai_ws.send(json.dumps({"type": "response.cancel"}))
                    response_busy = False
                    if stream_sid:
                        await websocket.send_text(
                            json.dumps({"event": "clear", "streamSid": stream_sid})
                        )
                elif event_type in (
                    "response.output_audio.delta",
                    "response.audio.delta",
                ):
                    if not stream_sid:
                        continue
                    await websocket.send_text(
                        json.dumps(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": data["delta"]},
                            }
                        )
                    )
                elif event_type in (
                    "response.done",
                    "response.cancelled",
                ):
                    response_busy = False
                elif event_type in (
                    "response.output_audio_transcript.delta",
                    "response.audio_transcript.delta",
                ):
                    delta = data.get("delta") or ""
                    if delta:
                        assistant_buf.append(delta)
                elif event_type in (
                    "response.output_audio_transcript.done",
                    "response.audio_transcript.done",
                ):
                    text = data.get("transcript") or "".join(assistant_buf)
                    assistant_buf.clear()
                    log.add("Cashe collections", text)
                    if GOODBYE_PHRASE_RE.search(text):
                        goodbye_said = True
                        log.add("system", "goodbye detected")
                        track(asyncio.create_task(auto_hangup_after_goodbye()))
                elif event_type == "response.function_call_arguments.done":
                    await handle_tool(
                        data.get("name") or "",
                        data.get("call_id") or "",
                        data.get("arguments") or "{}",
                    )
                    if hanging_up:
                        break
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    text = data.get("transcript") or ""
                    log.add("counterparty", text)
                    if on_hold and is_human_question(text):
                        cancel_active_wait()
                        log.add("system", "wait cancelled — human question")
                        await create_response(ANSWER_NOW_INSTRUCTIONS)
                    elif on_hold and text.strip() and not is_hold_filler(text):
                        cancel_active_wait()
                    if not dtmf_1_sent and is_english_ivr(text):
                        dtmf_1_sent = True
                        log.add("system", "auto DTMF 1 (IVR English)")
                        await send_dtmf_digit("1")
                    if not status_heard and not goodbye_said and looks_like_status_answer(text):
                        status_heard = True
                        log.add("system", "status answer heard — stay in the conversation")
                elif event_type == "error":
                    err = data.get("error") or {}
                    code = err.get("code")
                    if code == "conversation_already_has_active_response":
                        response_busy = True
                        print("OpenAI busy (ignored):", code, flush=True)
                    elif code != "response_cancel_not_active":
                        print("OpenAI error:", data, flush=True)
                        log.add("system", f"error: {err}")

        twilio_task = asyncio.create_task(twilio_to_openai())
        openai_task = asyncio.create_task(openai_to_twilio())
        done, pending = await asyncio.wait(
            [twilio_task, openai_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        hanging_up = True
        for task in list(bg_tasks):
            task.cancel()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, *bg_tasks, return_exceptions=True)
        for task in done:
            try:
                task.result()
            except Exception as exc:  # noqa: BLE001
                print("Bridge task ended:", exc, flush=True)
        log.close()
