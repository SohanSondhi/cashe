"""List Fireworks model ids available to this environment. Never prints secrets."""

import httpx

from cashe.config import settings


def main() -> None:
    if not settings.fireworks_api_key:
        print("no fireworks key")
        return
    response = httpx.get(
        f"{settings.fireworks_base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {settings.fireworks_api_key}"},
        timeout=30,
    )
    print("status", response.status_code)
    if response.status_code >= 400:
        print("error_len", len(response.text))
        return
    payload = response.json()
    rows = payload.get("data") or []
    print("count", len(rows))
    for row in rows:
        ident = row.get("id") if isinstance(row, dict) else None
        if ident:
            print(ident)


if __name__ == "__main__":
    main()
