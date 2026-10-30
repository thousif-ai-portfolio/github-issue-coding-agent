import pytest

from shopkit.inventory import Inventory, OutOfStockError


def test_cannot_reserve_more_than_in_stock():
    inventory = Inventory()
    inventory.restock("lamp", 2)
    with pytest.raises(OutOfStockError):
        inventory.reserve("lamp", 5)
    assert inventory.stock["lamp"] == 2
    with pytest.raises(OutOfStockError):
        inventory.reserve("chair", 1)
    inventory.reserve("lamp", 2)
    assert inventory.stock["lamp"] == 0
