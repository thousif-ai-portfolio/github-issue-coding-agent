import pytest

from shopkit.stats import percent_change


def test_percent_change_is_relative_to_the_old_value():
    assert percent_change(100, 150) == pytest.approx(50.0)
    assert percent_change(200, 100) == pytest.approx(-50.0)
    assert percent_change(80, 100) == pytest.approx(25.0)
