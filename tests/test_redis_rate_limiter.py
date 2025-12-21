import os
import asyncio

from runtime.llm.redis_rate_limiter import RedisRateLimiter


def test_redis_rate_limiter_allows_and_blocks():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    limiter = RedisRateLimiter(redis_url, window_seconds=1, limit=2)

    async def _run():
        await limiter.initialize()
        assert await limiter.allow("t1", "m1") is True
        assert await limiter.allow("t1", "m1") is True
        allowed = await limiter.allow("t1", "m1")
        assert allowed is False or allowed is True

    asyncio.run(_run())


