"""记忆管理服务：偏好、Skill 使用反馈和 Redis 工作区归档。

Planner 只负责判断是否需要沉淀记忆；本模块提供可复用的持久化入口，后续可由
记忆管理子 Agent 调用。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import GuardrailLog, SearchTask, SkillMemory, UserPreference, WorkingSession


async def upsert_user_preference(
    db: AsyncSession,
    *,
    user_id: int,
    key: str,
    value: Any,
    category: str = "implicit",
    confidence: float | None = None,
) -> UserPreference:
    """写入或更新用户偏好。"""

    existing = await db.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.key == key,
        )
    )
    if existing:
        existing.value = value
        existing.category = category
        existing.confidence = confidence
        existing.updated_at = datetime.utcnow()
        return existing

    preference = UserPreference(
        user_id=user_id,
        key=key,
        value=value,
        category=category,
        confidence=confidence,
    )
    db.add(preference)
    return preference


async def insert_skill_memory(
    db: AsyncSession,
    *,
    title: str,
    desc: str,
    content: str,
    citation: str | None = None,
    scope: str = "global",
    user_id: int | None = None,
    trigger_patterns: list[str] | None = None,
    confidence: float = 0.5,
) -> SkillMemory:
    """写入新的 Skill 记忆。"""

    skill = SkillMemory(
        title=title,
        desc=desc,
        content=content,
        citation=citation,
        scope=scope,
        user_id=user_id,
        trigger_patterns=trigger_patterns or [],
        confidence=confidence,
        status="active",
    )
    db.add(skill)
    return skill


async def update_skill_usage(
    db: AsyncSession,
    *,
    skill_id: int,
    succeeded: bool,
) -> SkillMemory | None:
    """更新 Skill 使用反馈。"""

    skill = await db.get(SkillMemory, skill_id)
    if not skill:
        return None

    skill.usage_count += 1
    if succeeded:
        skill.success_count += 1
    else:
        skill.fail_count += 1
    total = max(skill.success_count + skill.fail_count, 1)
    skill.confidence = skill.success_count / total
    skill.last_used_at = datetime.utcnow()
    return skill


async def archive_working_session(
    db: AsyncSession,
    redis: Redis,
    *,
    task: SearchTask,
) -> WorkingSession | None:
    """把 Redis 工作区归档到 zr_working_sessions。"""

    context_raw = await redis.get(f"task:{task.id}:context")
    logs_raw = await redis.get(f"task:{task.id}:working_log")
    if not context_raw and not logs_raw:
        return None

    context = json.loads(context_raw) if context_raw else {}
    logs = json.loads(logs_raw) if logs_raw else []
    if logs and isinstance(logs[0], str):
        steps = [{"step": index + 1, "action": item, "result": None, "timestamp": None} for index, item in enumerate(logs)]
    else:
        steps = logs

    _archive_guardrail_logs(db, task=task, logs=steps)

    session_key = f"task:{task.id}:working_log"
    existing = await db.scalar(select(WorkingSession).where(WorkingSession.session_key == session_key))
    if existing:
        existing.current_step = len(steps)
        existing.steps = steps
        existing.status = "archived"
        existing.ended_at = datetime.utcnow()
        return existing

    started_at = _parse_datetime(context.get("started_at")) or task.created_at or datetime.utcnow()
    session = WorkingSession(
        user_id=task.user_id,
        task_id=task.id,
        session_key=session_key,
        goal=context.get("query") or task.query or f"task:{task.id}",
        current_step=len(steps),
        steps=steps,
        tool_cache={},
        status="archived",
        started_at=started_at,
        ended_at=datetime.utcnow(),
    )
    db.add(session)
    return session


def _archive_guardrail_logs(db: AsyncSession, *, task: SearchTask, logs: list[dict[str, Any]]) -> None:
    """把 warning / critical 级护栏决策归档到 log_guardrail。"""

    for log in logs:
        if not isinstance(log, dict):
            continue

        decision = log.get("guardrail_decision")
        if not isinstance(decision, dict):
            continue

        alert_level = decision.get("alert_level")
        if alert_level not in {"warning", "critical"}:
            continue

        db.add(
            GuardrailLog(
                user_id=task.user_id,
                task_id=task.id,
                agent_name=log.get("agent") or decision.get("agent_name") or "worker",
                hook=decision.get("hook") or decision.get("stage") or log.get("interaction_type") or "unknown",
                operation=decision.get("operation"),
                tool_name=decision.get("tool_name"),
                allowed=bool(decision.get("allowed", False)),
                alert_level=alert_level,
                reason=decision.get("reason"),
                sanitized_payload=decision.get("sanitized_payload") or log.get("payload") or {},
                created_at=_parse_datetime(log.get("timestamp")) or datetime.utcnow(),
            )
        )


def _parse_datetime(value: str | None) -> datetime | None:
    """解析 Redis 中的 ISO 时间。"""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
