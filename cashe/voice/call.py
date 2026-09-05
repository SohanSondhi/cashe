"""Legacy Twilio ConversationRelay dialer (needs a TwiML /twiml server + ngrok).

Prefer realtime_twilio / call_twilio for OpenAI Realtime media streams.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from twilio.rest import Client

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(REPO_ROOT / ".env")


def twilio_client() -> Client:
    """
    Auth options (pick one):
      A) API Key:
         TWILIO_ACCOUNT_SID=ACxxx
         TWILIO_API_KEY=SKxxx
         TWILIO_API_SECRET=...
      B) Auth Token:
         TWILIO_ACCOUNT_SID=ACxxx
         TWILIO_AUTH_TOKEN=...
    """
    account = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    api_key = os.getenv("TWILIO_API_KEY", "").strip()
    api_secret = os.getenv("TWILIO_API_SECRET", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()

    if not account:
        sys.exit("Missing TWILIO_ACCOUNT_SID")

    if api_key and api_secret:
        return Client(api_key, api_secret, account_sid=account)

    if auth_token:
        return Client(account, auth_token)

    sys.exit(
        "Set either TWILIO_API_KEY + TWILIO_API_SECRET or TWILIO_AUTH_TOKEN"
    )


def main() -> None:
    from_number = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    to_number = (os.getenv("HARBORLINE_PHONE") or os.getenv("RESTAURANT_PHONE") or "").strip()
    host = os.getenv("PUBLIC_HOST", "").removeprefix("https://").removeprefix("http://").strip("/")
    send_digits = os.getenv("IVR_SEND_DIGITS", "").strip() or None

    missing = [
        name
        for name, val in [
            ("TWILIO_FROM_NUMBER", from_number),
            ("HARBORLINE_PHONE", to_number),
            ("PUBLIC_HOST", host),
        ]
        if not val
    ]
    if missing:
        sys.exit(f"Missing env: {', '.join(missing)}")

    twiml_url = f"https://{host}/twiml"
    client = twilio_client()

    kwargs: dict = {
        "to": to_number,
        "from_": from_number,
        "url": twiml_url,
    }
    if send_digits:
        kwargs["send_digits"] = send_digits

    call = client.calls.create(**kwargs)
    print(f"Calling {to_number} from {from_number}")
    print(f"TwiML: {twiml_url}")
    print(f"Call SID: {call.sid}")


if __name__ == "__main__":
    main()
