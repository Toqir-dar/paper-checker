"""Bloom filter for duplicate-upload detection on the upload stream."""

from __future__ import annotations

import hashlib
import math


class BloomFilter:
    """Simple bit-array Bloom filter with multiple hash functions."""

    def __init__(self, capacity: int = 10_000, error_rate: float = 0.01) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if not 0 < error_rate < 1:
            raise ValueError("error_rate must be in (0, 1)")
        self.capacity = capacity
        self.error_rate = error_rate
        # m = -n ln(p) / (ln 2)^2 ; k = (m/n) ln 2
        self.size = max(8, int(-capacity * math.log(error_rate) / (math.log(2) ** 2)))
        self.hash_count = max(1, int((self.size / capacity) * math.log(2)))
        self._bits = bytearray((self.size + 7) // 8)
        self.count = 0

    def _indexes(self, item: str) -> list[int]:
        digest = hashlib.sha256(item.encode("utf-8")).digest()
        # Derive k indexes from two 64-bit halves (Kirsch-Mitzenmacher).
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:16], "big") or 1
        return [((h1 + i * h2) % self.size) for i in range(self.hash_count)]

    def add(self, item: str) -> None:
        for idx in self._indexes(item):
            byte_i, bit_i = divmod(idx, 8)
            self._bits[byte_i] |= 1 << bit_i
        self.count += 1

    def might_contain(self, item: str) -> bool:
        for idx in self._indexes(item):
            byte_i, bit_i = divmod(idx, 8)
            if not (self._bits[byte_i] & (1 << bit_i)):
                return False
        return True

    def false_positive_rate_estimate(self) -> float:
        """Approximate FPR = (1 - e^(-kn/m))^k."""
        if self.size == 0:
            return 1.0
        return (1.0 - math.exp(-self.hash_count * self.count / self.size)) ** self.hash_count


def content_fingerprint(file_bytes: bytes, answer_texts: list[str] | None = None) -> str:
    """Stable hash used as Bloom membership key for an upload."""
    h = hashlib.sha256()
    h.update(file_bytes)
    if answer_texts:
        for text in answer_texts:
            h.update(b"\0")
            h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()
