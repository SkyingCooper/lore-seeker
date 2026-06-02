"""任务执行 Redis 工作区：Agent 间共享状态。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis

# 长期任务 30 天，一次性任务完成后 1 小时
TTL_RECURRING = 30 * 24 * 3600
TTL_ONESHOT = 3600


def _now():
    return datetime.now(timezone.utc).isoformat()


async def init_workspace(redis: Redis, task_id: int, context: dict) -> None:
    """任务开始执行时初始化所有 Redis key。"""
    context["started_at"] = _now()
    ttl = TTL_RECURRING if context.get("frequency") != "once" else TTL_ONESHOT

    await redis.setex(f"task:{task_id}:context", ttl, json.dumps(context))
    await redis.setex(f"task:{task_id}:subtasks", ttl, json.dumps({"total": 0, "completed": 0, "failed": 0, "items": []}))
    await redis.setex(f"task:{task_id}:results_raw", ttl, json.dumps([]))
    await redis.setex(f"task:{task_id}:results_refined", ttl, json.dumps([]))
    await redis.setex(f"task:{task_id}:working_log", ttl, json.dumps([]))


async def update_context(redis: Redis, task_id: int, **kwargs) -> None:
    raw = await redis.get(f"task:{task_id}:context")
    if raw:
        ctx = json.loads(raw)
        ctx.update(kwargs)
        ttl = await redis.ttl(f"task:{task_id}:context")
        await redis.setex(f"task:{task_id}:context", max(ttl, 60), json.dumps(ctx))


async def get_context(redis: Redis, task_id: int) -> dict | None:
    raw = await redis.get(f"task:{task_id}:context")
    return json.loads(raw) if raw else None


async def set_subtasks(redis: Redis, task_id: int, items: list) -> None:
    total = len(items)
    ctx = await get_context(redis, task_id)
    ttl = TTL_RECURRING if ctx and ctx.get("frequency") != "once" else TTL_ONESHOT
    await redis.setex(f"task:{task_id}:subtasks", ttl, json.dumps({
        "total": total, "completed": 0, "failed": 0, "items": items,
    }))


async def update_subtask(redis: Redis, task_id: int, subtask_id: str, **kwargs) -> None:
    raw = await redis.get(f"task:{task_id}:subtasks")
    if not raw:
        return
    data = json.loads(raw)
    for item in data["items"]:
        if item["id"] == subtask_id:
            item.update(kwargs)
            break
    data["completed"] = sum(1 for i in data["items"] if i["status"] == "done")
    data["failed"] = sum(1 for i in data["items"] if i["status"] == "failed")
    ctx = await get_context(redis, task_id)
    ttl = TTL_RECURRING if ctx and ctx.get("frequency") != "once" else TTL_ONESHOT
    await redis.setex(f"task:{task_id}:subtasks", ttl, json.dumps(data))


async def append_raw_results(redis: Redis, task_id: int, results: list) -> None:
    raw = await redis.get(f"task:{task_id}:results_raw")
    existing = json.loads(raw) if raw else []
    existing.extend(results)
    ctx = await get_context(redis, task_id)
    ttl = TTL_RECURRING if ctx and ctx.get("frequency") != "once" else TTL_ONESHOT
    await redis.setex(f"task:{task_id}:results_raw", ttl, json.dumps(existing))


async def get_raw_results(redis: Redis, task_id: int) -> list:
    raw = await redis.get(f"task:{task_id}:results_raw")
    return json.loads(raw) if raw else []


async def set_refined_results(redis: Redis, task_id: int, results: list) -> None:
    ctx = await get_context(redis, task_id)
    ttl = TTL_RECURRING if ctx and ctx.get("frequency") != "once" else TTL_ONESHOT
    await redis.setex(f"task:{task_id}:results_refined", ttl, json.dumps(results))


async def append_log(redis: Redis, task_id: int, agent: str, message: str) -> None:
    raw = await redis.get(f"task:{task_id}:working_log")
    logs = json.loads(raw) if raw else []
    logs.append(f"[{_now()}][{agent}] {message}")
    ctx = await get_context(redis, task_id)
    ttl = TTL_RECURRING if ctx and ctx.get("frequency") != "once" else TTL_ONESHOT
    await redis.setex(f"task:{task_id}:working_log", ttl, json.dumps(logs))


async def are_all_subtasks_done(redis: Redis, task_id: int) -> bool:
    raw = await redis.get(f"task:{task_id}:subtasks")
    if not raw:
        return False
    data = json.loads(raw)
    return data["completed"] + data["failed"] >= data["total"]


async def has_any_subtask_succeeded(redis: Redis, task_id: int) -> bool:
    raw = await redis.get(f"task:{task_id}:subtasks")
    if not raw:
        return False
    data = json.loads(raw)
    return data["completed"] > 0


async def cleanup_workspace(redis: Redis, task_id: int) -> None:
    for suffix in ("context", "subtasks", "results_raw", "results_refined", "working_log"):
        await redis.delete(f"task:{task_id}:{suffix}")


# ─── LLM 缓存 ─────────────────────────────────────────────────────────────

async def get_llm_cache(redis: Redis, model: str, prompt: str) -> str | None:
    import hashlib
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:32]
    return await redis.get(f"llm:cache:{model}:{prompt_hash}")


async def set_llm_cache(redis: Redis, model: str, prompt: str, result: str, ttl: int = 7 * 24 * 3600) -> None:
    import hashlib
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:32]
    await redis.setex(f"llm:cache:{model}:{prompt_hash}", ttl, result)
