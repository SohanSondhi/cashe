from cashe.fixtures.world import HARBORLINE_VOICE


def mock_voice_call(objective: str, allowed_questions: list[str], turn_budget: int) -> dict:
    """Return a completed voice investigation without a live telephony agent."""
    data = HARBORLINE_VOICE
    used = min(len(data["transcript"]), turn_budget)
    return {
        "mocked": True,
        "live": False,
        "agent": "voice",
        "note": "Live telephony was not configured; returning the HarborLine fixture transcript.",
        "source_id": "harborline-ap-desk",
        "objective": objective,
        "allowed_questions": allowed_questions,
        "turn_budget": turn_budget,
        "turns_used": used,
        "speaker_identity_claim": data["claimed_speaker"],
        "transcript": data["transcript"][:used],
        "extracted": {
            "invoice_number": data["invoice_number"],
            "status": data["status"],
            "blocking_reason": data["reason"],
            "promised_follow_up": data["promised_follow_up"],
            "payment_date": data["payment_date"],
            "can_issue_authoritative_document": False,
        },
        "promised_follow_up": data["promised_follow_up"],
        "authority": "COMMUNICATION",
        "confidence": "provisional",
        "requires_documentary_corroboration": True,
        "provider": "mock",
    }
