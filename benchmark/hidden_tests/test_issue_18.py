from shopkit.cart import Cart


def test_removing_a_missing_item_does_nothing():
    cart = Cart()
    cart.add("pen", 150)
    cart.remove("mug")
    cart.remove("pen")
    cart.remove("pen")
    assert cart.total() == 0
