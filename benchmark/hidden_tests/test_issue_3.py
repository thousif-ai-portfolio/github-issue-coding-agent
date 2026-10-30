from shopkit.money import format_price


def test_format_price_pads_cents():
    assert format_price(1205) == "$12.05"
    assert format_price(100) == "$1.00"
    assert format_price(-5) == "-$0.05"
