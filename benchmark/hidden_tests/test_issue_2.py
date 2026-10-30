from shopkit.text import truncate


def test_truncate_counts_the_suffix():
    assert truncate("Wireless headphones", 10) == "Wireles..."
    assert truncate("short", 10) == "short"
