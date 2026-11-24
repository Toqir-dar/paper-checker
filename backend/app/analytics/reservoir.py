"""Reservoir sampling over a stream of graded answers for QA audit lists."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class ReservoirSampler(Generic[T]):
    """Vitter's Algorithm R — uniform sample of size k from an unknown stream."""

    k: int
    seed: int | None = None

    def __post_init__(self) -> None:
        if self.k < 1:
            raise ValueError("k must be >= 1")
        self._rng = random.Random(self.seed)
        self._sample: list[T] = []
        self._seen = 0

    def offer(self, item: T) -> None:
        self._seen += 1
        if len(self._sample) < self.k:
            self._sample.append(item)
            return
        j = self._rng.randint(1, self._seen)
        if j <= self.k:
            self._sample[j - 1] = item

    @property
    def sample(self) -> list[T]:
        return list(self._sample)

    @property
    def seen(self) -> int:
        return self._seen
