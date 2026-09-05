from cashe.voice.place_call import build_voice_payload, place_voice_call
from cashe.voice.realtime_common import caller_instructions, first_message


def test_purpose_is_fstringed_into_caller_prompt():
    purpose = "Ask whether PO-HL-2207 is matched yet"
    prompt = caller_instructions(purpose, ["What is the current status?"])
    assert "PURPOSE OF THIS CALL" in prompt
    assert purpose in prompt
    assert "What is the current status?" in prompt
    assert "INV-HL-3301" not in prompt
    assert "Marta" not in prompt


def test_first_message_uses_purpose():
    purpose = "Confirm invoice status and request written confirmation"
    assert purpose in first_message(purpose)
    assert "INV-HL-3301" not in first_message(purpose)


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


def test_place_voice_call_falls_back_to_mock_without_destination(monkeypatch):
    monkeypatch.setattr("cashe.voice.place_call.live_destination", lambda source_phone="": "")
    payload = place_voice_call("Why is INV-HL-3301 unpaid?", [], 8, source_id="harborline-ap-desk")
    assert payload["mocked"] is True
    assert payload["transcript"]
    assert payload["purpose"] == "Why is INV-HL-3301 unpaid?"
