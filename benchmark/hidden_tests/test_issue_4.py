from shopkit.money import apply_discount


def test_discount_never_goes_below_zero():
    assert apply_discount(1000, 150) == 0
    assert apply_discount(1000, 100) == 0
    assert apply_discount(1000, 25) == 750
