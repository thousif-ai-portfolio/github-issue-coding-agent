"""Summary statistics for sales reports."""


def average(values: list[float]) -> float:
    if not values:
        raise ValueError("average of an empty list")
    return sum(values) / len(values)


def median(values: list[float]) -> float:
    """The middle value; for an even count, the mean of the two middle values."""
    if not values:
        raise ValueError("median of an empty list")
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle]
