"""Normalization used for exact recovery. Not a paraphrase threshold."""

from __future__ import annotations

import hashlib
import unicodedata


def norm(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text or "").split()).casefold()


def contains_text(haystack: str, needle: str) -> bool:
    n = norm(needle)
    return bool(n) and n in norm(haystack)


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()
