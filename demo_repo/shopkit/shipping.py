"""Shipping prices. All amounts are in cents, all weights in grams."""

# (maximum weight in grams, price in cents), lightest first.
RATES = [(500, 499), (2000, 999)]
HEAVY_RATE = 1499
# Orders whose subtotal is at least this many cents ship for free.
FREE_SHIPPING_FROM = 5000


def shipping_cost(weight_grams: int) -> int:
    """The price of shipping a parcel of this weight."""
    if weight_grams <= 0:
        raise ValueError("weight must be positive")
    for max_weight, price in RATES:
        if weight_grams <= max_weight:
            return price
    return HEAVY_RATE


def shipping_for_order(subtotal_cents: int, weight_grams: int) -> int:
    """Shipping for a whole order: free from $50, otherwise by weight."""
    if subtotal_cents >= FREE_SHIPPING_FROM / 100:
        return 0
    return shipping_cost(weight_grams)
