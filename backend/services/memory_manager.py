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

from core.embedding_router import get_embeddings_with_usage
from core.llm_router import get_llm
from core.prompt_loader import get_prompt, render_prompt
from constraint.validation.validator import validate_db_contract
from agents.token_usage import merge_stage_usage, usage_from_response
from db.models import (
    EpisodicLog,
    GuardrailLog,
    SearchTask,
    SemanticMemory,
    SkillMemory,
    TokenConsumptionLog,
    UserTokenBalance,
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
    caller: str = "memory_manager",
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
            caller=caller,
        )

    for skill_id in _used_skill_ids(topic_config, state):
        await update_skill_usage(db, skill_id=skill_id, succeeded=succeeded, caller=caller)

    quality_score = float(state.get("quality_score") or 0)
    if succeeded and quality_score >= _excellent_task_score_threshold():
        await _write_excellent_task_skill(db, task=task, state=state, quality_score=quality_score, caller=caller)

    if succeeded:
        await _extract_and_store_llm_memories(db, redis, task=task, state=state, caller=caller)

    await record_token_consumption(db, task=task, state=state, caller=caller)

    return await archive_working_session(db, redis, task=task, caller=caller)


async def record_token_consumption(
    db: AsyncSession,
    *,
    task: SearchTask,
    state: dict[str, Any],
    caller: str = "memory_manager",
) -> TokenConsumptionLog:
    """任务结束后扣减用户 token 余额并写入按 stage 拆分的消耗流水。"""

    user_id = str(task.user_id)
    task_id = str(task.id)
    estimated_before = _estimated_token_total(state)
    token_usage = state.get("token_usage") or {}
    actual_consumed = _actual_token_total(token_usage)

    balance = await db.get(UserTokenBalance, user_id)
    if not balance:
        balance = UserTokenBalance(
            user_id=user_id,
            balance=0,
            total_consumed=0,
            last_reset_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(balance)

    starting_balance = int(balance.balance or 0)
    balance_after = max(starting_balance - actual_consumed, 0)
    validate_db_contract(
        "record_token_consumption",
        caller=caller,
        operation="insert_or_update",
        payload={
            "user_id": user_id,
            "task_id": task_id,
            "estimated_before": estimated_before,
            "actual_consumed": actual_consumed,
            "balance_after": balance_after,
            "stage": "summary",
        },
    )

    balance.balance = balance_after
    balance.total_consumed = int(balance.total_consumed or 0) + actual_consumed
    balance.updated_at = datetime.utcnow()

    logs = _build_token_logs(
        user_id=user_id,
        task_id=task_id,
        estimated_before=estimated_before,
        starting_balance=starting_balance,
        token_usage=token_usage,
        cost_usage=state.get("cost_usage") or {},
    )
    for log in logs:
        db.add(log)
    if not logs:
        log = TokenConsumptionLog(
            user_id=user_id,
            task_id=task_id,
            stage="summary",
            estimated_before=estimated_before,
            actual_consumed=actual_consumed,
            balance_after=balance_after,
            metadata_={"token_usage": token_usage},
        )
        db.add(log)
        return log
    return logs[-1]


async def _extract_and_store_llm_memories(
    db: AsyncSession,
    redis: Redis,
    *,
    task: SearchTask,
    state: dict[str, Any],
    caller: str,
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
        state["token_usage"] = merge_stage_usage(
            state.get("token_usage"),
            stage="memory_manager",
            usage=usage_from_response(resp),
            model=getattr(llm, "model_name", None),
        )
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
                caller=caller,
            )

        await _insert_semantic_memories(
            db,
            task=task,
            state=state,
            items=_safe_list(extracted.get("semantic_memories")),
            caller=caller,
        )
        for item in _safe_list(extracted.get("episodic_logs")):
            await insert_episodic_log(
                db,
                user_id=task.user_id,
                task_id=task.id,
                event_type=str(item.get("event_type") or "task_run"),
                content=str(item.get("content") or "")[:4000],
                importance=_clamp_float(item.get("importance"), default=0.5),
                metadata={"source": "memory_manager.extract"},
                caller=caller,
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
    state: dict[str, Any],
    items: list[dict[str, Any]],
    caller: str,
) -> None:
    valid_items = [
        item
        for item in items
        if item.get("title") and item.get("summary") and item.get("content")
    ]
    if not valid_items:
        return

    summaries = [str(item["summary"]) for item in valid_items]
    embeddings, usage = await get_embeddings_with_usage(summaries)
    state["token_usage"] = merge_stage_usage(
        state.get("token_usage"),
        stage="memory_manager",
        usage=usage,
        model=None,
    )
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
            caller=caller,
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
    caller: str = "memory_manager",
) -> EpisodicLog:
    """写入情景记忆日志。"""

    validate_db_contract(
        "insert_episodic_log",
        caller=caller,
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
    caller: str = "memory_manager",
) -> SemanticMemory:
    """写入语义记忆。"""

    validate_db_contract(
        "insert_semantic_memory",
        caller=caller,
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


def _estimated_token_total(state: dict[str, Any]) -> int:
    """从任务状态中读取预估 token 消耗，缺失时使用实际消耗兜底。"""

    for key in ("estimated_token_usage", "token_estimate", "estimated_tokens"):
        value = state.get(key)
        if isinstance(value, dict):
            value = value.get("total")
        number = _safe_int(value)
        if number > 0:
            return number

    topic_config = state.get("topic_config") or {}
    for key in ("estimated_token_usage", "token_estimate", "estimated_tokens"):
        value = topic_config.get(key)
        if isinstance(value, dict):
            value = value.get("total")
        number = _safe_int(value)
        if number > 0:
            return number

    return _actual_token_total(state.get("token_usage"))


def _actual_token_total(token_usage: Any) -> int:
    """读取 reports.token_usage.total；没有 total 时汇总 breakdown。"""

    if not isinstance(token_usage, dict):
        return 0

    total = _safe_int(token_usage.get("total"))
    if total > 0:
        return total

    breakdown = token_usage.get("breakdown")
    if not isinstance(breakdown, dict):
        return 0
    return sum(_safe_int(item.get("total") if isinstance(item, dict) else item) for item in breakdown.values())


def _build_token_logs(
    *,
    user_id: str,
    task_id: str,
    estimated_before: int,
    starting_balance: int,
    token_usage: dict[str, Any],
    cost_usage: dict[str, Any] | None = None,
) -> list[TokenConsumptionLog]:
    breakdown = token_usage.get("breakdown") if isinstance(token_usage, dict) else None
    model_used = token_usage.get("model_used") if isinstance(token_usage, dict) else None
    cost_breakdown = cost_usage.get("breakdown") if isinstance(cost_usage, dict) else None
    if not isinstance(breakdown, dict):
        return []

    logs: list[TokenConsumptionLog] = []
    remaining_balance = starting_balance
    for stage, item in breakdown.items():
        if not isinstance(item, dict):
            continue
        stage_total = _safe_int(item.get("total"))
        if stage_total <= 0:
            continue
        remaining_balance = max(remaining_balance - stage_total, 0)
        model_name = model_used.get(stage) if isinstance(model_used, dict) else None
        logs.append(
            TokenConsumptionLog(
                user_id=user_id,
                task_id=task_id,
                stage=str(stage),
                provider=_provider_from_model(model_name),
                model=model_name,
                input_tokens=_safe_int(item.get("input_tokens")),
                output_tokens=_safe_int(item.get("output_tokens")),
                estimated_before=estimated_before,
                actual_consumed=stage_total,
                balance_after=remaining_balance,
                metadata_={
                    "timestamp": token_usage.get("timestamp"),
                    "stage_breakdown": item,
                    "cost_usage": (cost_breakdown or {}).get(stage) if isinstance(cost_breakdown, dict) else None,
                },
            )
        )
    return logs


def _safe_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _provider_from_model(model_name: Any) -> str | None:
    if not model_name:
        return None
    text = str(model_name).lower()
    if "qwen" in text or "dashscope" in text:
        return "aliyun"
    if "gpt" in text or "openai" in text:
        return "openai"
    if "gemini" in text:
        return "gemini"
    if "deepseek" in text:
        return "deepseek"
    if "rule_based" in text:
        return "local"
    return None


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
    caller: str,
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
            caller=caller,
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
        caller=caller,
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
    caller: str = "memory_manager",
) -> UserPreference:
    """写入或更新用户偏好。"""

    validate_db_contract(
        "upsert_user_preference",
        caller=caller,
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
    caller: str = "memory_manager",
) -> SkillMemory:
    """写入新的 Skill 记忆。"""

    validate_db_contract(
        "insert_skill_memory",
        caller=caller,
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
    caller: str = "memory_manager",
) -> SkillMemory | None:
    """更新 Skill 使用反馈。"""

    validate_db_contract(
        "update_skill_memory_usage",
        caller=caller,
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
    caller: str = "memory_manager",
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

    _archive_guardrail_logs(db, task=task, logs=steps, caller=caller)

    session_key = f"task:{task.id}:working_log"
    validate_db_contract(
        "archive_working_session",
        caller=caller,
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


def _archive_guardrail_logs(
    db: AsyncSession,
    *,
    task: SearchTask,
    logs: list[dict[str, Any]],
    caller: str,
) -> None:
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
                caller=caller,
            )
        )


def _guardrail_log(
    *,
    task: SearchTask,
    log: dict[str, Any],
    decision: dict[str, Any],
    alert_level: str,
    caller: str,
) -> GuardrailLog:
    validate_db_contract(
        "insert_guardrail_log",
        caller=caller,
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
