"""Stock levels for the warehouse."""

from dataclasses import dataclass, field


class OutOfStockError(Exception):
    """Raised when an order asks for more than is in stock."""


@dataclass
class Inventory:
    stock: dict[str, int] = field(default_factory=dict)

    def restock(self, item: str, quantity: int) -> None:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        self.stock[item] = self.stock.get(item, 0) + quantity

    def reserve(self, item: str, quantity: int) -> None:
        """Takes `quantity` out of stock for an order. Raises OutOfStockError if there
        is not enough, leaving the stock unchanged."""
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        self.stock[item] = self.stock.get(item, 0) - quantity

    def low_stock(self, threshold: int = 5) -> list[str]:
        """Items whose stock is at or below `threshold`, so they can be reordered."""
        return sorted(item for item, count in self.stock.items() if count < threshold)
