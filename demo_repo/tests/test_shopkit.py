"""The repo's own tests. They pass, because none of them covers a planted bug."""

from datetime import date

import pytest

from shopkit.cart import Cart
from shopkit.dates import add_business_days, is_weekend, parse_date
from shopkit.inventory import Inventory
from shopkit.money import apply_discount, format_price, parse_price, split_evenly
from shopkit.shipping import shipping_cost, shipping_for_order
from shopkit.stats import average, median, percent_change, top_n
from shopkit.text import normalize_whitespace, slugify, truncate


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


def test_normalize_whitespace_collapses_spaces():
    assert normalize_whitespace("  big   red  mug ") == "big red mug"


def test_parse_price_and_split_evenly():
    assert parse_price("$12.34") == 1234
    assert parse_price("7") == 700
    assert split_evenly(900, 3) == [300, 300, 300]
    with pytest.raises(ValueError):
        split_evenly(100, 0)


def test_parse_date_rejects_garbage():
    with pytest.raises(ValueError):
        parse_date("not a date")


def test_percent_change_and_top_n():
    assert percent_change(100, 100) == 0
    with pytest.raises(ValueError):
        percent_change(0, 5)
    assert sorted(top_n({"a": 1, "b": 2}, 5)) == ["a", "b"]


def test_inventory_restock_and_reserve():
    inventory = Inventory()
    inventory.restock("lamp", 3)
    inventory.restock("lamp", 2)
    inventory.reserve("lamp", 4)
    assert inventory.stock["lamp"] == 1
    assert inventory.low_stock(3) == ["lamp"]


def test_shipping_cost_by_weight():
    assert shipping_cost(300) == 499
    assert shipping_cost(2000) == 999
    assert shipping_cost(2500) == 1499
    assert shipping_for_order(10000, 2500) == 0
