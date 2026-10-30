from shopkit.cart import Cart


def test_adding_an_item_again_increases_its_quantity():
    cart = Cart()
    cart.add("apple", 50, quantity=2)
    cart.add("apple", 50, quantity=3)
    assert cart.quantities["apple"] == 5
    assert cart.total() == 250
