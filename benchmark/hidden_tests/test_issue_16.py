from shopkit.inventory import Inventory


def test_low_stock_includes_items_at_the_threshold():
    inventory = Inventory({"pen": 5, "mug": 4, "cap": 6})
    assert inventory.low_stock(5) == ["mug", "pen"]
