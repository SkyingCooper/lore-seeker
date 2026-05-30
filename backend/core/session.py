from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis

SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 天


async def create_guest_session(redis: Redis, user_id: str) -> str:
    session_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    data = {"user_id": user_id, "is_guest": True, "created_at": now, "last_access_at": now}
    await redis.setex(f"session:{session_id}", SESSION_TTL_SECONDS, json.dumps(data))
    return session_id


async def get_session(redis: Redis, session_id: str) -> dict | None:
    raw = await redis.get(f"session:{session_id}")
    if raw is None:
        return None
    # 刷新 TTL 和 last_access_at
    data = json.loads(raw)
    data["last_access_at"] = datetime.now(timezone.utc).isoformat()
    await redis.setex(f"session:{session_id}", SESSION_TTL_SECONDS, json.dumps(data))
    return data


async def delete_session(redis: Redis, session_id: str) -> None:
    await redis.delete(f"session:{session_id}")
