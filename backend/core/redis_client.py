from __future__ import annotations

import redis.asyncio as aioredis
from redis.asyncio import Redis

from core.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis
