"""记忆管理子 Agent：负责 Planner handoff 后的记忆持久化与归档。

该模块把任务收尾阶段的偏好、Skill、语义/情景记忆、工作区归档和 token 结算
收敛为一个独立 Agent 单元。Worker 只负责调度，Planner 负责生成 handoff contract，
真正的持久化动作统一由 memory_manager Agent 执行。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from agents.guardrails import (
    AgentErrorContext,
    AgentOutputContext,
    AgentRunContext,
    after_run,
    before_run,
    build_guarded_pydantic_agent,
    on_error,
)
from constraint.validation.validator import validate_agent_result, validate_agent_task
from core.task_redis import append_log
from db.models import SearchTask
from services.memory_manager import run_task_memory_manager


MEMORY_MANAGER_AGENT = build_guarded_pydantic_agent(
    "memory_manager",
    instructions=(
        "You are the Lore Seeker memory manager subagent. "
        "Accept only planner handoff payloads, persist memories within declared contracts, "
        "archive task workspaces, and record token settlement. Never execute search, report generation, "
        "or cross-user data access."
    ),
)


class MemoryManagerExtension(BaseModel):
    """Memory manager specific handoff payload carried in agent.task.extensions."""

    trigger: str = "task_finalize"
    succeeded: bool
    quality_score: float = 0.0
    has_organized_md: bool = False
    persist_working_session: bool = True
    extract_llm_memories: bool = False
    used_skill_ids: list[int] = Field(default_factory=list)
    token_usage: dict[str, Any] = Field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_memory_manager_handoff(
    task: SearchTask,
    final_state: dict[str, Any] | None = None,
    *,
    succeeded: bool,
    trigger: str = "task_finalize",
) -> dict[str, Any]:
    """生成 Planner -> Memory Manager 的标准 agent.task contract。"""

    state = final_state or {}
    topic_config = state.get("topic_config") or {}
    source_sites = task.source_sites or topic_config.get("source_sites") or []
    status = "completed" if succeeded else "failed"
    extension = MemoryManagerExtension(
        trigger=trigger,
        succeeded=succeeded,
        quality_score=float(state.get("quality_score") or 0.0),
        has_organized_md=bool(state.get("organized_md")),
        persist_working_session=True,
        extract_llm_memories=bool(succeeded and state.get("organized_md")),
        used_skill_ids=_normalize_skill_ids(state, topic_config),
        token_usage=state.get("token_usage") or {},
    )
    payload = {
        "schema_version": "1.0",
        "contract_type": "agent.task",
        "trace": {
            "trace_id": f"task:{task.id}:memory",
            "created_at": _now(),
        },
        "task": {
            "task_id": task.id,
            "topic_id": task.topic_id,
            "user_id": task.user_id,
            "title": str(task.query or topic_config.get("title") or f"task:{task.id}")[:255],
            "keywords": topic_config.get("keywords") or [],
            "description": topic_config.get("description"),
            "source_sites": source_sites,
            "search_mode": task.search_mode or topic_config.get("search_mode") or "mixed",
            "frequency": task.frequency or topic_config.get("frequency") or "once",
            "status": status,
            "created_at": _now(),
            "metadata": {
                "query": task.query or state.get("query"),
                "trigger": trigger,
                "quality_feedback": state.get("quality_feedback"),
            },
        },
        "routing": {
            "from_agent": "planner",
            "to_agent": "memory_manager",
            "handoff_reason": "persist task memories, archive workspace, and settle token usage",
            "next_action": "archive",
        },
        "extensions": {
            "memory_manager": extension.model_dump(),
        },
    }
    return validate_agent_task(payload)


async def run_memory_manager_agent(
    db: AsyncSession,
    redis: Redis,
    *,
    task: SearchTask,
    final_state: dict[str, Any] | None = None,
    succeeded: bool,
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行独立的记忆管理子 Agent。"""

    state = final_state or {}
    handoff_payload = handoff or build_memory_manager_handoff(task, state, succeeded=succeeded)
    validate_agent_task(handoff_payload)
    memory_handoff = MemoryManagerExtension.model_validate(
        (handoff_payload.get("extensions") or {}).get("memory_manager") or {"succeeded": succeeded}
    )
    operation = "process_memory_handoff"
    guardrail_state = {
        "task": {
            "task_id": handoff_payload["task"]["task_id"],
            "user_id": handoff_payload["task"]["user_id"],
            "status": handoff_payload["task"]["status"],
        },
        "memory_handoff": memory_handoff.model_dump(),
        "topic_config": state.get("topic_config") or {},
        "quality_score": float(state.get("quality_score") or 0.0),
        "token_usage": state.get("token_usage") or {},
        "succeeded": succeeded,
    }
    decision = before_run(
        AgentRunContext(
            agent_name="memory_manager",
            responsibility="memory_persistence",
            operation=operation,
            user_id=task.user_id,
            task_id=task.id,
            state=guardrail_state,
        )
    )
    await append_log(
        redis,
        int(task.id),
        "memory_manager",
        "Planner 已生成记忆管理子任务",
        interaction_type="agent_handoff",
        status="running",
        guardrail_decision=decision.model_dump(),
        payload={
            "trigger": memory_handoff.trigger,
            "handoff_reason": handoff_payload["routing"]["handoff_reason"],
            "task_status": handoff_payload["task"]["status"],
        },
    )

    try:
        session = await run_task_memory_manager(
            db,
            redis,
            task=task,
            final_state=state,
            succeeded=succeeded,
            caller="memory_manager",
        )
        result = validate_agent_result(
            {
                "schema_version": "1.0",
                "contract_type": "agent.result",
                "trace": {
                    "trace_id": f"task:{task.id}:memory_result",
                    "created_at": _now(),
                },
                "task_id": task.id,
                "producer_agent": "memory_manager",
                "status": "succeeded",
                "next_action": "complete",
                "metrics": {
                    "finished_at": _now(),
                    "token_usage": int(
                        (memory_handoff.token_usage or {}).get("breakdown", {})
                        .get("memory_manager", {})
                        .get("total", 0)
                    ),
                },
                "metadata": {
                    "trigger": memory_handoff.trigger,
                    "succeeded": succeeded,
                    "quality_score": memory_handoff.quality_score,
                    "working_session_id": getattr(session, "id", None),
                    "archived_working_session": bool(session),
                    "extract_llm_memories": memory_handoff.extract_llm_memories,
                    "used_skill_ids": memory_handoff.used_skill_ids,
                },
                "extensions": {
                    "memory_manager": memory_handoff.model_dump(),
                },
            }
        )
        after = after_run(
            AgentOutputContext(
                agent_name="memory_manager",
                operation=operation,
                result=result,
            )
        )
        await append_log(
            redis,
            int(task.id),
            "memory_manager",
            "记忆管理子 Agent 执行完成",
            interaction_type="status_update",
            status="completed",
            guardrail_decision=after.model_dump(),
            payload={
                "working_session_id": getattr(session, "id", None),
                "trigger": memory_handoff.trigger,
            },
        )
        return result
    except Exception as exc:
        error = on_error(
            AgentErrorContext(
                agent_name="memory_manager",
                stage="on_error",
                operation=operation,
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=False,
            )
        )
        await append_log(
            redis,
            int(task.id),
            "memory_manager",
            "记忆管理子 Agent 执行失败",
            interaction_type="error",
            status="failed",
            guardrail_decision=error.model_dump(),
            payload={"trigger": memory_handoff.trigger},
        )
        raise


def _normalize_skill_ids(state: dict[str, Any], topic_config: dict[str, Any]) -> list[int]:
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
