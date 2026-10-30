from datetime import date

from shopkit.dates import parse_date


def test_dates_are_day_first():
    assert parse_date("31/10/2026") == date(2026, 10, 31)
    assert parse_date("05/11/2026") == date(2026, 11, 5)
