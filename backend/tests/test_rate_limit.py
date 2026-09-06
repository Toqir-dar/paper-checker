import pytest

from app.core.rate_limit import InMemoryRateLimiter, RateLimitExceededError


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()

    await limiter.check(["ip:127.0.0.1", "email:user@example.com"], 2, 60)
    await limiter.check(["ip:127.0.0.1", "email:user@example.com"], 2, 60)

    with pytest.raises(RateLimitExceededError) as error:
        await limiter.check(["ip:127.0.0.1", "email:user@example.com"], 2, 60)

    assert error.value.retry_after >= 1


@pytest.mark.asyncio
async def test_rate_limiter_applies_limits_per_key() -> None:
    limiter = InMemoryRateLimiter()

    await limiter.check(["ip:127.0.0.1", "email:first@example.com"], 1, 60)
    await limiter.check(["ip:192.0.2.1", "email:second@example.com"], 1, 60)

    with pytest.raises(RateLimitExceededError):
        await limiter.check(["ip:127.0.0.1", "email:other@example.com"], 1, 60)
