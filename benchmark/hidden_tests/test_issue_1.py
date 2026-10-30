from shopkit.text import slugify


def test_slugify_collapses_runs_of_symbols():
    assert slugify("Blue T-Shirt (Large)") == "blue-t-shirt-large"
    assert slugify("  Hello,   World!  ") == "hello-world"
