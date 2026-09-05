import secrets
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None = None) -> str:
    d = dt or utcnow()
    if d.tzinfo is None:
        return d.isoformat() + "Z"
    return d.isoformat()
