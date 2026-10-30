from shopkit.money import split_evenly


def test_shares_add_up_to_the_bill():
    assert split_evenly(1000, 3) == [334, 333, 333]
    assert split_evenly(1001, 4) == [251, 250, 250, 250]
    assert split_evenly(900, 3) == [300, 300, 300]
    for cents, people in [(1000, 3), (7, 5), (12345, 7)]:
        shares = split_evenly(cents, people)
        assert sum(shares) == cents
        assert max(shares) - min(shares) <= 1
