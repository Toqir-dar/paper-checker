"""k-shingles and Jaccard similarity for near-duplicate detection."""

from __future__ import annotations


def normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def k_shingles(text: str, k: int = 5) -> set[str]:
    """Character k-shingles over whitespace-normalized text."""
    if k < 1:
        raise ValueError("k must be >= 1")
    cleaned = normalize_text(text)
    if not cleaned:
        return set()
    if len(cleaned) < k:
        return {cleaned}
    return {cleaned[i : i + k] for i in range(len(cleaned) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0
