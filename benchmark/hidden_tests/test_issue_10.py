from shopkit.money import parse_price


def test_prices_with_thousands_separators():
    assert parse_price("$1,234.56") == 123456
    assert parse_price("1,000,000") == 100000000
    assert parse_price("12.5") == 1250
