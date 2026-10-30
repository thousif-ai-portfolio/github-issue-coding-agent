from shopkit.text import normalize_whitespace


def test_tabs_and_newlines_become_single_spaces():
    assert normalize_whitespace("Soft\tcotton\n\nshirt") == "Soft cotton shirt"
    assert normalize_whitespace("  a \t\n b  ") == "a b"
    assert normalize_whitespace("plain text") == "plain text"
