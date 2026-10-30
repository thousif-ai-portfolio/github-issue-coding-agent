from shopkit.stats import median


def test_median_of_even_count_is_mean_of_middle_pair():
    assert median([1, 2, 3, 4]) == 2.5
    assert median([4, 1]) == 2.5
    assert median([5, 1, 3]) == 3
