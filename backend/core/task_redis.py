"""任务执行 Redis 工作区：Agent 间共享状态。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis

from constraint.validation.validator import validate_redis_value

# 长期任务 30 天，一次性任务完成后 1 小时
TTL_RECURRING = 30 * 24 * 3600
TTL_ONESHOT = 3600


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ttl_for_context(context: dict | None) -> int:
    return TTL_RECURRING if context and context.get("frequency") != "once" else TTL_ONESHOT


def _normalize_guardrail_decision(decision: dict | None) -> dict | None:
    if not decision:
        return None

    alert_level = decision.get("alert_level") or "info"
    if alert_level == "none":
        alert_level = "info"

    return {
        "hook": decision.get("hook") or decision.get("stage") or "unknown",
        "allowed": bool(decision.get("allowed", False)),
        "alert_level": alert_level,
        "reason": decision.get("reason"),
        "operation": decision.get("operation"),
        "tool_name": decision.get("tool_name"),
    }


async def _set_json(redis: Redis, key: str, ttl: int, value: object, contract_definition: str) -> None:
    validate_redis_value(value, contract_definition)
    await redis.setex(key, ttl, json.dumps(value, ensure_ascii=False))


async def init_workspace(redis: Redis, task_id: int, context: dict) -> None:
    """任务开始执行时初始化所有 Redis key。"""
    context["started_at"] = _now()
    ttl = TTL_RECURRING if context.get("frequency") != "once" else TTL_ONESHOT

    await _set_json(redis, f"task:{task_id}:context", ttl, context, "task_context")
    await _set_json(
        redis,
        f"task:{task_id}:subtasks",
        ttl,
        {"total": 0, "completed": 0, "failed": 0, "items": []},
        "task_subtasks",
    )
    await _set_json(redis, f"task:{task_id}:results_raw", ttl, [], "task_results")
    await _set_json(redis, f"task:{task_id}:results_refined", ttl, [], "task_results")
    await _set_json(redis, f"task:{task_id}:working_log", ttl, [], "working_log")


async def update_context(redis: Redis, task_id: int, **kwargs) -> None:
    raw = await redis.get(f"task:{task_id}:context")
    if raw:
        ctx = json.loads(raw)
        ctx.update(kwargs)
        ctx["updated_at"] = _now()
        ttl = await redis.ttl(f"task:{task_id}:context")
        await _set_json(redis, f"task:{task_id}:context", max(ttl, 60), ctx, "task_context")


async def get_context(redis: Redis, task_id: int) -> dict | None:
    raw = await redis.get(f"task:{task_id}:context")
    return json.loads(raw) if raw else None


async def set_subtasks(redis: Redis, task_id: int, items: list) -> None:
    total = len(items)
    ctx = await get_context(redis, task_id)
    ttl = _ttl_for_context(ctx)
    data = {
        "total": total, "completed": 0, "failed": 0, "items": items,
    }
    await _set_json(redis, f"task:{task_id}:subtasks", ttl, data, "task_subtasks")


async def update_subtask(redis: Redis, task_id: int, subtask_id: str, **kwargs) -> None:
    raw = await redis.get(f"task:{task_id}:subtasks")
    if not raw:
        return
    data = json.loads(raw)
    for item in data["items"]:
        if item.get("id") == subtask_id or item.get("subtask_id") == subtask_id:
            item.update(kwargs)
            break
    data["completed"] = sum(1 for i in data["items"] if i["status"] in {"done", "succeeded"})
    data["failed"] = sum(1 for i in data["items"] if i["status"] == "failed")
    ctx = await get_context(redis, task_id)
    ttl = _ttl_for_context(ctx)
    await _set_json(redis, f"task:{task_id}:subtasks", ttl, data, "task_subtasks")


async def append_raw_results(redis: Redis, task_id: int, results: list) -> None:
    raw = await redis.get(f"task:{task_id}:results_raw")
    existing = json.loads(raw) if raw else []
    existing.extend(results)
    ctx = await get_context(redis, task_id)
    ttl = _ttl_for_context(ctx)
    await _set_json(redis, f"task:{task_id}:results_raw", ttl, existing, "task_results")


async def get_raw_results(redis: Redis, task_id: int) -> list:
    raw = await redis.get(f"task:{task_id}:results_raw")
    return json.loads(raw) if raw else []


async def set_refined_results(redis: Redis, task_id: int, results: list) -> None:
    ctx = await get_context(redis, task_id)
    ttl = _ttl_for_context(ctx)
    await _set_json(redis, f"task:{task_id}:results_refined", ttl, results, "task_results")


async def append_log(
    redis: Redis,
    task_id: int,
    agent: str,
    message: str,
    *,
    interaction_type: str | None = None,
    status: str | None = None,
    tool_name: str | None = None,
    mcp_server: str | None = None,
    guardrail_decision: dict | None = None,
    payload: dict | None = None,
) -> None:
    raw = await redis.get(f"task:{task_id}:working_log")
    logs = json.loads(raw) if raw else []
    logs.append({
        "timestamp": _now(),
        "agent": agent,
        "event": message,
        "interaction_type": interaction_type,
        "tool_name": tool_name,
        "mcp_server": mcp_server,
        "status": status,
        "guardrail_decision": _normalize_guardrail_decision(guardrail_decision),
        "payload": payload or {},
    })
    ctx = await get_context(redis, task_id)
    ttl = _ttl_for_context(ctx)
    await _set_json(redis, f"task:{task_id}:working_log", ttl, logs, "working_log")


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
