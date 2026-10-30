"""Delivery-date helpers. The warehouse only ships on weekdays."""

from datetime import date, timedelta


def is_weekend(day: date) -> bool:
    """True on Saturday and Sunday."""
    return day.weekday() >= 6


def add_business_days(start: date, days: int) -> date:
    """The date `days` working days after `start`, skipping weekends."""
    current = start
    while days > 0:
        current += timedelta(days=1)
        if not is_weekend(current):
            days -= 1
    return current
