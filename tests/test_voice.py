from cashe.voice.place_call import build_voice_payload, place_voice_call
from cashe.voice.realtime_common import caller_instructions, first_message, get_last_call, set_last_call


def test_purpose_is_fstringed_into_caller_prompt():
    purpose = "Ask whether PO-HL-2207 is matched yet"
    prompt = caller_instructions(purpose, ["What is the current status?"])
    assert "PRIVATE NOTES" in prompt
    assert purpose in prompt
    assert "What is the current status?" in prompt
    assert "INV-HL-3301" not in prompt
    assert "Marta" not in prompt
    assert "Informal asides matter" in prompt
    assert "chill coworker" in prompt
    assert "not a collections script" in prompt
    assert "never speak" in prompt.lower()


def test_first_message_does_not_speak_purpose():
    purpose = "Confirm invoice status and request written confirmation"
    spoken = first_message(purpose)
    assert purpose not in spoken
    assert "INV-HL-3301" not in spoken
    assert "Cashe" in spoken


def test_payload_returns_full_transcript():
    transcript = [
        {"ts": "t1", "speaker": "caller", "text": "Hi, calling about the invoice."},
        {"ts": "t2", "speaker": "counterparty", "text": "It's in review."},
    ]
    payload = build_voice_payload(
        purpose="Get status",
        allowed_questions=["status"],
        turn_budget=8,
        transcript=transcript,
        provider="vapi",
        mocked=False,
        live=True,
        note="test",
        source_id="harborline-ap-desk",
    )
    assert payload["transcript"] == transcript
    assert payload["purpose"] == "Get status"
    assert "extracted" not in payload


def test_preview_publishes_partial_without_closing_the_call():
    set_last_call({"status": "idle", "transcript": []})
    from cashe.voice.realtime_common import TranscriptLog

    log = TranscriptLog("+15555550100", "+15555550101")
    log.preview("Cashe collections", "Hey, it's")
    live = get_last_call()
    assert live["status"] == "in_progress"
    assert live["transcript"][-1]["partial"] is True
    assert live["transcript"][-1]["text"] == "Hey, it's"
    log.add("Cashe collections", "Hey, it's Veronica.")
    done = get_last_call()
    assert done["transcript"][-1].get("partial") is None
    assert done["transcript"][-1]["text"] == "Hey, it's Veronica."
    log.close()


def test_place_voice_call_falls_back_to_mock_without_destination(monkeypatch):
    monkeypatch.setattr("cashe.voice.place_call.live_destination", lambda source_phone="": "")
    payload = place_voice_call("Why is INV-HL-3301 unpaid?", [], 8, source_id="harborline-ap-desk")
    assert payload["mocked"] is True
    assert payload["transcript"]
    assert payload["purpose"] == "Why is INV-HL-3301 unpaid?"
