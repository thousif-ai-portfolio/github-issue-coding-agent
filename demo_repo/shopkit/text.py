"""Text helpers for product names and descriptions."""

import re


def slugify(text: str) -> str:
    """Turns a product name into a URL slug: "Blue T-Shirt (Large)" -> "blue-t-shirt-large"."""
    slug = re.sub(r"[^a-z0-9]", "-", text.lower())
    return slug.strip("-")


def truncate(text: str, length: int, suffix: str = "...") -> str:
    """Shortens text to at most `length` characters, ending with `suffix` when it is cut."""
    if len(text) <= length:
        return text
    return text[:length] + suffix
