"""记忆管理服务：偏好、Skill 使用反馈和 Redis 工作区归档。

Planner 只负责判断是否需要沉淀记忆；本模块提供可复用的持久化入口，后续可由
记忆管理子 Agent 调用。
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, SystemMessage

from core.embedding_router import get_embeddings
from core.llm_router import get_llm
from core.prompt_loader import get_prompt, render_prompt
from constraint.validation.validator import validate_db_contract
from db.models import (
    EpisodicLog,
    GuardrailLog,
    SearchTask,
    SemanticMemory,
    SkillMemory,
    UserPreference,
    WorkingSession,
)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "celery.yaml"


async def run_task_memory_manager(
    db: AsyncSession,
    redis: Redis,
    *,
    task: SearchTask,
    final_state: dict[str, Any] | None = None,
    succeeded: bool,
) -> WorkingSession | None:
    """任务收尾阶段的记忆管理子 Agent 入口。

    当前版本只处理确定性数据：显式偏好、Skill 使用反馈、高分任务经验和工作区归档。
    需要 LLM 判断的隐式偏好抽取可在此入口内继续扩展。
    """

    state = final_state or {}
    topic_config = state.get("topic_config") or {}
    for key, value in _iter_declared_preferences(topic_config):
        await upsert_user_preference(
            db,
            user_id=task.user_id,
            key=key,
            value=value,
            category="explicit",
            confidence=None,
        )

    for skill_id in _used_skill_ids(topic_config, state):
        await update_skill_usage(db, skill_id=skill_id, succeeded=succeeded)

    quality_score = float(state.get("quality_score") or 0)
    if succeeded and quality_score >= _excellent_task_score_threshold():
        await _write_excellent_task_skill(db, task=task, state=state, quality_score=quality_score)

    if succeeded:
        await _extract_and_store_llm_memories(db, redis, task=task, state=state)

    return await archive_working_session(db, redis, task=task)


async def _extract_and_store_llm_memories(
    db: AsyncSession,
    redis: Redis,
    *,
    task: SearchTask,
    state: dict[str, Any],
) -> None:
    """调用小模型抽取隐式偏好、语义记忆和情景日志。"""

    if not state.get("organized_md"):
        return

    try:
        llm = get_llm(temperature=0.1)
        system_prompt = get_prompt("memory_manager.extract.system")
        user_prompt = render_prompt(
            "memory_manager.extract.user",
            task_id=task.id,
            user_id=task.user_id,
            query=task.query or state.get("query") or "",
            topic_config=state.get("topic_config") or {},
            quality_score=state.get("quality_score") or 0,
            quality_feedback=state.get("quality_feedback") or "",
            organized_md=str(state.get("organized_md") or "")[:6000],
        )
        resp = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
        extracted = json.loads(resp.content)
    except Exception as exc:
        from core.task_redis import append_log

        await append_log(
            redis,
            int(task.id),
            "worker",
            "记忆管理子 Agent 隐式记忆抽取失败",
            interaction_type="error",
            status="failed",
            payload={"error_type": type(exc).__name__, "message": str(exc)},
        )
        return

    try:
        for item in _safe_list(extracted.get("preferences")):
            key = item.get("key")
            if not key:
                continue
            await upsert_user_preference(
                db,
                user_id=task.user_id,
                key=str(key),
                value=item.get("value"),
                category="implicit",
                confidence=_clamp_float(item.get("confidence"), default=0.5),
            )

        await _insert_semantic_memories(db, task=task, items=_safe_list(extracted.get("semantic_memories")))
        for item in _safe_list(extracted.get("episodic_logs")):
            await insert_episodic_log(
                db,
                user_id=task.user_id,
                task_id=task.id,
                event_type=str(item.get("event_type") or "task_run"),
                content=str(item.get("content") or "")[:4000],
                importance=_clamp_float(item.get("importance"), default=0.5),
                metadata={"source": "memory_manager.extract"},
            )
    except Exception as exc:
        from core.task_redis import append_log

        await append_log(
            redis,
            int(task.id),
            "worker",
            "记忆管理子 Agent 记忆写入失败",
            interaction_type="error",
            status="failed",
            payload={"error_type": type(exc).__name__, "message": str(exc)},
        )


async def _insert_semantic_memories(
    db: AsyncSession,
    *,
    task: SearchTask,
    items: list[dict[str, Any]],
) -> None:
    valid_items = [
        item
        for item in items
        if item.get("title") and item.get("summary") and item.get("content")
    ]
    if not valid_items:
        return

    summaries = [str(item["summary"]) for item in valid_items]
    embeddings = await get_embeddings(summaries)
    for item, embedding in zip(valid_items, embeddings):
        await insert_semantic_memory(
            db,
            user_id=task.user_id,
            title=str(item["title"])[:500],
            summary=str(item["summary"]),
            content=str(item["content"]),
            embedding=embedding,
            confidence=_clamp_float(item.get("confidence"), default=0.5),
            source_type="task",
            source_id=task.id,
        )


async def insert_episodic_log(
    db: AsyncSession,
    *,
    user_id: int,
    event_type: str,
    content: str,
    importance: float,
    task_id: int | None = None,
    session_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EpisodicLog:
    """写入情景记忆日志。"""

    validate_db_contract(
        "insert_episodic_log",
        caller="planner",
        operation="insert",
        payload={
            "user_id": user_id,
            "event_type": event_type,
            "content": content,
            "importance": importance,
            "task_id": task_id,
            "session_key": session_key,
            "metadata": metadata or {},
        },
    )
    log = EpisodicLog(
        user_id=user_id,
        task_id=task_id,
        session_key=session_key,
        event_type=event_type,
        content=content,
        importance=importance,
        metadata_=metadata or {},
    )
    db.add(log)
    return log


async def insert_semantic_memory(
    db: AsyncSession,
    *,
    user_id: int,
    title: str,
    summary: str,
    content: str,
    embedding: list[float],
    confidence: float,
    source_type: str | None = None,
    source_id: int | None = None,
) -> SemanticMemory:
    """写入语义记忆。"""

    validate_db_contract(
        "insert_semantic_memory",
        caller="planner",
        operation="insert",
        payload={
            "user_id": user_id,
            "title": title,
            "summary": summary,
            "content": content,
            "embedding": embedding,
            "confidence": confidence,
            "source_type": source_type,
            "source_id": source_id,
        },
    )
    memory = SemanticMemory(
        user_id=user_id,
        title=title,
        summary=summary,
        content=content,
        embedding=embedding,
        source_type=source_type,
        source_id=source_id,
        confidence=confidence,
        last_accessed=datetime.utcnow(),
    )
    db.add(memory)
    return memory


def _iter_declared_preferences(topic_config: dict[str, Any]) -> list[tuple[str, Any]]:
    preferences = topic_config.get("user_preferences") or topic_config.get("preferences") or {}
    if not isinstance(preferences, dict):
        return []
    return [(str(key), value) for key, value in preferences.items()]


def _safe_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _clamp_float(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(0.0, min(1.0, number))


def _used_skill_ids(topic_config: dict[str, Any], state: dict[str, Any]) -> list[int]:
    raw_ids = state.get("used_skill_ids") or topic_config.get("used_skill_ids") or topic_config.get("skill_ids") or []
    if not isinstance(raw_ids, list):
        return []
    ids: list[int] = []
    for item in raw_ids:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


async def _write_excellent_task_skill(
    db: AsyncSession,
    *,
    task: SearchTask,
    state: dict[str, Any],
    quality_score: float,
) -> SkillMemory:
    title = f"高质量任务经验：{(task.query or state.get('query') or f'task:{task.id}')[:80]}"
    existing = await db.scalar(
        select(SkillMemory).where(
            SkillMemory.title == title,
            SkillMemory.scope == "user",
            SkillMemory.user_id == task.user_id,
            SkillMemory.status == "active",
        )
    )
    content = _build_skill_content(task=task, state=state, quality_score=quality_score)
    desc = f"任务 {task.id} 质量评分 {quality_score:.0f}，可复用其规划、搜索和整理策略。"
    if existing:
        validate_db_contract(
            "upsert_skill_memory",
            caller="planner",
            operation="insert_or_update",
            payload={
                "title": title,
                "desc": desc,
                "content": content,
                "scope": "user",
                "trigger_patterns": [task.query] if task.query else [],
                "user_id": task.user_id,
                "confidence": max(float(existing.confidence or 0.5), 0.8),
            },
        )
        existing.desc = desc
        existing.content = content
        existing.confidence = max(float(existing.confidence or 0.5), 0.8)
        existing.updated_at = datetime.utcnow()
        return existing

    return await insert_skill_memory(
        db,
        title=title,
        desc=desc,
        content=content,
        citation=f"source_task_id={task.id}; quality_score={quality_score:.0f}",
        scope="user",
        user_id=task.user_id,
        trigger_patterns=[task.query] if task.query else [],
        confidence=0.8,
    )


def _build_skill_content(*, task: SearchTask, state: dict[str, Any], quality_score: float) -> str:
    topic_config = state.get("topic_config") or {}
    plan = topic_config.get("_plan") or {}
    return "\n".join(
        [
            f"任务：{task.query or state.get('query') or task.id}",
            f"质量评分：{quality_score:.0f}",
            f"搜索模式：{topic_config.get('search_mode') or task.search_mode}",
            f"来源站点：{', '.join(topic_config.get('source_sites') or task.source_sites or [])}",
            f"规划查询：{', '.join(plan.get('search_queries') or [])}",
            f"重点方向：{', '.join(plan.get('focus_areas') or [])}",
            "复用建议：优先复用本次已验证的查询拆解、来源选择、章节组织和质量检查反馈。",
        ]
    )


def _excellent_task_score_threshold() -> float:
    if not CONFIG_PATH.exists():
        return 95.0
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return float(((data.get("celery") or {}).get("memory_policy") or {}).get("excellent_task_score_threshold", 95))


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

    validate_db_contract(
        "upsert_user_preference",
        caller="planner",
        operation="insert_or_update",
        payload={"user_id": user_id, "key": key, "value": value, "category": category},
    )
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

    validate_db_contract(
        "insert_skill_memory",
        caller="planner",
        operation="insert",
        payload={
            "title": title,
            "desc": desc,
            "content": content,
            "scope": scope,
            "trigger_patterns": trigger_patterns or [],
            "citation": citation,
            "user_id": user_id,
            "confidence": confidence,
        },
    )
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

    validate_db_contract(
        "update_skill_memory_usage",
        caller="planner",
        operation="update",
        payload={
            "usage_count": 1,
            "success_count": 1 if succeeded else 0,
            "fail_count": 0 if succeeded else 1,
            "last_used_at": datetime.utcnow(),
            "status": "active",
            "confidence": 0.5,
        },
    )
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
    validate_db_contract(
        "archive_working_session",
        caller="worker",
        operation="insert",
        payload={
            "user_id": task.user_id,
            "session_key": session_key,
            "goal": context.get("query") or task.query or f"task:{task.id}",
            "steps": steps,
            "started_at": _parse_datetime(context.get("started_at")) or task.created_at or datetime.utcnow(),
        },
    )
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
            _guardrail_log(
                task=task,
                log=log,
                decision=decision,
                alert_level=alert_level,
            )
        )


def _guardrail_log(
    *,
    task: SearchTask,
    log: dict[str, Any],
    decision: dict[str, Any],
    alert_level: str,
) -> GuardrailLog:
    validate_db_contract(
        "insert_guardrail_log",
        caller="worker",
        operation="insert",
        payload={
            "agent_name": log.get("agent") or decision.get("agent_name") or "worker",
            "hook": decision.get("hook") or decision.get("stage") or log.get("interaction_type") or "unknown",
            "allowed": bool(decision.get("allowed", False)),
            "alert_level": alert_level,
            "sanitized_payload": decision.get("sanitized_payload") or log.get("payload") or {},
        },
    )
    return GuardrailLog(
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


def _parse_datetime(value: str | None) -> datetime | None:
    """解析 Redis 中的 ISO 时间。"""

    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
