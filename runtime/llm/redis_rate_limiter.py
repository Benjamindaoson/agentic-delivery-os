"""
Simple Redis-backed fixed-window rate limiter for per-tenant/per-model quotas.
This implements an approximate fixed-window counter:
 - key = "rl:{tenant_id}:{model}:{window_start}"
 - INCR and check against limit
"""
import os
import time
from typing import Optional
try:
    import redis.asyncio as aioredis
except Exception:
    aioredis = None

class RedisRateLimiter:
    def __init__(self, redis_url: str, window_seconds: int = 1, limit: int = 5):
        # If redis async client unavailable, operate in permissive/no-op mode
        self._disabled = False
        if aioredis is None:
            self._disabled = True
        self.redis_url = redis_url
        self.window_seconds = int(window_seconds)
        self.limit = int(limit)
        self._client = None

    async def initialize(self):
        if self._disabled:
            return
        if self._client is None:
            self._client = aioredis.from_url(self.redis_url)

    async def allow(self, tenant_id: str = "default", model: str = "default") -> bool:
        if self._disabled:
            return True
        await self.initialize()
        now = int(time.time())
        window_start = now - (now % self.window_seconds)
        key = f"rl:{tenant_id}:{model}:{window_start}"
        try:
            val = await self._client.incr(key)
            if val == 1:
                # set expiry so key auto-expires
                await self._client.expire(key, self.window_seconds + 1)
            return val <= self.limit
        except Exception:
            # On redis error, be permissive
            return True


