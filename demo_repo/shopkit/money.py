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
