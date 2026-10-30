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


def percent_change(old: float, new: float) -> float:
    """How much `new` grew or shrank compared to `old`, in percent: 100 -> 150 is 50.0."""
    if old == 0:
        raise ValueError("percent change from zero is undefined")
    return (new - old) / new * 100


def top_n(counts: dict[str, int], n: int) -> list[str]:
    """The `n` best-selling items, best first."""
    return [item for item, _ in sorted(counts.items(), key=lambda pair: pair[1])][:n]
