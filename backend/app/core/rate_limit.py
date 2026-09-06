import asyncio
import time
from collections import defaultdict, deque


class RateLimitExceededError(Exception):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__("Rate limit exceeded")


class InMemoryRateLimiter:
    """A process-local sliding-window limiter for low-volume security endpoints."""

    def __init__(self, max_keys: int = 10_000) -> None:
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._max_keys = max_keys

    async def check(self, keys: list[str], limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        unique_keys = set(keys)

        async with self._lock:
            for key in unique_keys:
                attempts = self._attempts[key]
                while attempts and attempts[0] <= cutoff:
                    attempts.popleft()
                if len(attempts) >= limit:
                    retry_after = max(1, int(attempts[0] + window_seconds - now) + 1)
                    raise RateLimitExceededError(retry_after)

            for key in unique_keys:
                self._attempts[key].append(now)

            if len(self._attempts) > self._max_keys:
                self._attempts = defaultdict(
                    deque,
                    {
                        key: attempts
                        for key, attempts in self._attempts.items()
                        if attempts and attempts[-1] > cutoff
                    },
                )

    async def clear(self) -> None:
        async with self._lock:
            self._attempts.clear()
