"""A shopping cart that totals its items and applies a bulk discount."""

from dataclasses import dataclass, field

from shopkit.money import apply_discount

# Carts with this many items or more get BULK_DISCOUNT_PERCENT off the total.
BULK_THRESHOLD = 10
BULK_DISCOUNT_PERCENT = 10


@dataclass
class Cart:
    prices: dict[str, int] = field(default_factory=dict)
    quantities: dict[str, int] = field(default_factory=dict)

    def add(self, item: str, price_cents: int, quantity: int = 1) -> None:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        self.prices[item] = price_cents
        self.quantities[item] = quantity

    def remove(self, item: str) -> None:
        del self.prices[item]
        del self.quantities[item]

    def item_count(self) -> int:
        return sum(self.quantities.values())

    def total(self) -> int:
        subtotal = sum(self.prices[item] * qty for item, qty in self.quantities.items())
        if self.item_count() > BULK_THRESHOLD:
            return apply_discount(subtotal, BULK_DISCOUNT_PERCENT)
        return subtotal
