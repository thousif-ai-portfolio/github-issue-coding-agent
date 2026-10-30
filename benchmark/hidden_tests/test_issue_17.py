from shopkit.shipping import shipping_for_order


def test_free_shipping_starts_at_fifty_dollars():
    assert shipping_for_order(500, 300) == 499
    assert shipping_for_order(4999, 1500) == 999
    assert shipping_for_order(5000, 1500) == 0
