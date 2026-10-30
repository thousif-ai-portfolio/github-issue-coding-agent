from shopkit.stats import top_n


def test_top_n_lists_best_sellers_first():
    counts = {"mug": 5, "pen": 40, "cap": 12, "bag": 1}
    assert top_n(counts, 2) == ["pen", "cap"]
    assert top_n(counts, 1) == ["pen"]
