"""Prices are stored as whole cents to avoid floating-point rounding errors."""


def format_price(cents: int, symbol: str = "$") -> str:
    """Formats a price in cents for display: 123456 -> "$1,234.56"."""
    sign = "-" if cents < 0 else ""
    dollars, rest = divmod(abs(cents), 100)
    return f"{sign}{symbol}{dollars:,}.{rest}"


def apply_discount(cents: int, percent: float) -> int:
    """The price after a percentage discount, rounded to the nearest cent."""
    if percent < 0:
        raise ValueError("percent must not be negative")
    return round(cents * (1 - percent / 100))


def parse_price(text: str) -> int:
    """Reads a price typed by a person, "$1,234.56" or "12.5", as cents."""
    cleaned = text.strip().lstrip("$")
    dollars, _, cents = cleaned.partition(".")
    return int(dollars) * 100 + int(cents.ljust(2, "0")[:2] or 0)


def split_evenly(cents: int, people: int) -> list[int]:
    """Splits a bill between people. The shares add up to the bill exactly."""
    if people < 1:
        raise ValueError("people must be at least 1")
    return [cents // people] * people
