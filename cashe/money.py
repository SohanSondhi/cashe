def usd(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.0f}" if abs(cents) % 100 == 0 else f"{sign}${abs(cents) / 100:,.2f}"


def usd_millions(cents: int) -> str:
    millions = cents / 100 / 1_000_000
    text = f"{millions:.2f}".rstrip("0").rstrip(".")
    return f"${text} million"


def pct(part: int | float, whole: int | float, digits: int = 1) -> float:
    if whole == 0:
        return 0.0
    return round(part / whole * 100, digits)
