from __future__ import annotations

import re
import unicodedata


def normalize_text(value: str) -> str:
    """Normalize text for case/diacritics-insensitive matching."""
    value = value.strip().lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())
