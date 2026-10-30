from shopkit.cart import Cart


def test_bulk_discount_starts_at_ten_items():
    cart = Cart()
    cart.add("pen", 100, quantity=10)
    assert cart.total() == 900
    cart.add("mug", 100)
    assert cart.total() == 990
