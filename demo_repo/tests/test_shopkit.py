"""The repo's own tests. They pass, because none of them covers a planted bug."""

from datetime import date

import pytest

from shopkit.cart import Cart
from shopkit.dates import add_business_days, is_weekend
from shopkit.money import apply_discount, format_price
from shopkit.stats import average, median
from shopkit.text import slugify, truncate


def test_slugify_simple_names():
    assert slugify("Hello") == "hello"
    assert slugify("blue shirt") == "blue-shirt"


def test_truncate_leaves_short_text_alone():
    assert truncate("short", 10) == "short"


def test_format_price():
    assert format_price(1250) == "$12.50"
    assert format_price(123456) == "$1,234.56"


def test_apply_discount():
    assert apply_discount(1000, 10) == 900
    with pytest.raises(ValueError):
        apply_discount(1000, -5)


def test_cart_total_and_remove():
    cart = Cart()
    cart.add("mug", 800)
    cart.add("pen", 150, quantity=2)
    assert cart.total() == 1100
    cart.remove("pen")
    assert cart.total() == 800


def test_cart_bulk_discount_for_large_orders():
    cart = Cart()
    cart.add("pen", 100, quantity=12)
    assert cart.total() == 1080


def test_dates():
    assert is_weekend(date(2026, 11, 1))  # Sunday
    assert not is_weekend(date(2026, 11, 4))  # Wednesday
    assert add_business_days(date(2026, 11, 2), 2) == date(2026, 11, 4)


def test_stats():
    assert average([1, 2, 3]) == 2
    assert median([3, 1, 2]) == 2
