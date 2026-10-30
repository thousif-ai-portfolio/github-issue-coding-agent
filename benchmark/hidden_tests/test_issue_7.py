from datetime import date

from shopkit.dates import add_business_days, is_weekend


def test_saturday_is_a_weekend_day():
    assert is_weekend(date(2026, 10, 31))  # Saturday
    assert not is_weekend(date(2026, 10, 30))  # Friday
    assert add_business_days(date(2026, 10, 30), 1) == date(2026, 11, 2)
