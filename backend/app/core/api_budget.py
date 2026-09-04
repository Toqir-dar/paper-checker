import asyncio
import time
from collections import deque

from app.config import settings


class ApiBudgetExceededError(RuntimeError):
    """The configured request budget cannot accept another API call."""


class ApiRequestBudget:
    """Process-wide sliding-window limiter for outbound model requests."""

    def __init__(self, requests_per_minute: int, requests_per_day: int) -> None:
        self._per_minute = requests_per_minute
        self._per_day = requests_per_day
        self._timestamps: deque[float] = deque()
        self._day_timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                day_cutoff = now - 86400
                minute_cutoff = now - 60
                while self._day_timestamps and self._day_timestamps[0] <= day_cutoff:
                    self._day_timestamps.popleft()
                while self._timestamps and self._timestamps[0] <= minute_cutoff:
                    self._timestamps.popleft()

                if len(self._day_timestamps) >= self._per_day:
                    raise ApiBudgetExceededError("Daily model API request limit reached")
                if len(self._timestamps) < self._per_minute:
                    self._timestamps.append(now)
                    self._day_timestamps.append(now)
                    return
                wait_for = self._timestamps[0] + 60 - now

            await asyncio.sleep(max(wait_for, 0.01))


request_budget = ApiRequestBudget(settings.model_requests_per_minute, settings.model_requests_per_day)