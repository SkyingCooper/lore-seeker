"""Agent 交互契约适配器。

LangGraph 节点内部仍使用轻量 state 传递；本模块负责在节点边界生成标准
agent.task / agent.result envelope，并通过 backend/constraint 的 JSON Schema 校验。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from constraint.validation.validator import validate_agent_result, validate_agent_task


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _task_base(state: dict[str, Any]) -> dict[str, Any]:
    topic_config = state.get("topic_config") or {}
    title = state.get("query") or topic_config.get("title") or f"task:{state.get('task_id')}"
    return {
        "task_id": state.get("task_id"),
        "topic_id": topic_config.get("topic_id"),
        "user_id": state.get("user_id"),
        "title": str(title)[:255],
        "keywords": topic_config.get("keywords") or [],
        "description": topic_config.get("description"),
        "source_sites": topic_config.get("source_sites") or [],
        "search_mode": topic_config.get("search_mode") or "mixed",
        "frequency": topic_config.get("frequency") or "once",
        "status": topic_config.get("status") or "fetching",
        "created_at": _now(),
        "metadata": {"raw_topic_config": topic_config},
    }


def validate_worker_to_planner_task(state: dict[str, Any]) -> dict[str, Any]:
    """校验 Worker -> Planner 的初始任务 envelope。"""

    payload = {
        "schema_version": "1.0",
        "contract_type": "agent.task",
        "trace": {"trace_id": f"task:{state.get('task_id')}", "created_at": _now()},
        "task": _task_base(state),
        "routing": {
            "from_agent": "worker",
            "to_agent": "planner",
            "handoff_reason": "start task planning",
            "next_action": "plan",
        },
        "extensions": {},
    }
    return validate_agent_task(payload)


def validate_planner_to_searcher_task(state: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """校验 Planner -> Searcher 的搜索任务 envelope。"""

    search_queries = plan.get("search_queries") or [state.get("query")]
    source_sites = (state.get("topic_config") or {}).get("source_sites") or []
    subtasks = [
        {
            "subtask_id": f"search-{index + 1}",
            "keyword": str(query),
            "source_sites": source_sites,
            "search_mode": (state.get("topic_config") or {}).get("search_mode") or "mixed",
            "priority": 3,
            "reason": "planner generated query",
            "status": "pending",
            "retry_policy": {"max_attempts": 3, "backoff": "exponential", "timeout_seconds": 60},
            "metadata": {},
        }
        for index, query in enumerate(search_queries)
        if query
    ]
    payload = {
        "schema_version": "1.0",
        "contract_type": "agent.task",
        "trace": {"trace_id": f"task:{state.get('task_id')}:plan", "created_at": _now()},
        "task": _task_base(state),
        "planning": {
            "intent_summary": plan.get("intent_summary") or state.get("query") or "",
            "needs_query_optimization": bool(plan.get("needs_query_optimization", False)),
            "needs_decomposition": bool(plan.get("needs_decomposition", len(subtasks) > 1)),
            "focus_areas": plan.get("focus_areas") or [],
            "expected_chapters": plan.get("expected_chapters") or [],
            "search_queries": [item["keyword"] for item in subtasks] or [state.get("query")],
            "planner_notes": plan.get("planner_notes"),
        },
        "subtasks": subtasks,
        "routing": {
            "from_agent": "planner",
            "to_agent": "searcher",
            "handoff_reason": "execute structured search plan",
            "next_action": "search",
        },
        "extensions": {},
    }
    return validate_agent_task(payload)


def validate_searcher_result(state: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    """校验 Searcher -> Organizer 的搜索结果 envelope。"""

    payload = {
        "schema_version": "1.0",
        "contract_type": "agent.result",
        "trace": {"trace_id": f"task:{state.get('task_id')}:search", "created_at": _now()},
        "task_id": state.get("task_id"),
        "producer_agent": "searcher",
        "status": "succeeded" if results else "partial",
        "search": {
            "summary": f"searcher returned {len(results)} result(s)",
            "results": [_normalize_search_result(item) for item in results[:100]],
            "histories": [],
        },
        "next_action": "organize",
        "metrics": {"finished_at": _now()},
        "metadata": {},
        "extensions": {},
    }
    return validate_agent_result(payload)


def validate_organizer_result(state: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    """校验 Organizer -> Planner/Worker 的报告结果 envelope。"""

    payload = {
        "schema_version": "1.0",
        "contract_type": "agent.result",
        "trace": {"trace_id": f"task:{state.get('task_id')}:organizer", "created_at": _now()},
        "task_id": state.get("task_id"),
        "producer_agent": "organizer",
        "status": "succeeded" if output.get("organized_md") else "failed",
        "organizer": {
            "title": state.get("query"),
            "content_md": output.get("organized_md"),
            "toc": output.get("toc") or [],
            "summary": None,
            "quality_score": None,
            "quality_feedback": None,
            "pass": None,
        },
        "next_action": "complete",
        "metrics": {"finished_at": _now(), "token_usage": (output.get("token_usage") or {}).get("total", 0)},
        "metadata": {},
        "extensions": {},
    }
    return validate_agent_result(payload)


def validate_quality_result(state: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    """校验 Planner 质量检查输出 envelope。"""

    payload = {
        "schema_version": "1.0",
        "contract_type": "agent.result",
        "trace": {"trace_id": f"task:{state.get('task_id')}:quality", "created_at": _now()},
        "task_id": state.get("task_id"),
        "producer_agent": "planner",
        "status": "succeeded" if output.get("final") else "partial",
        "organizer": {
            "title": state.get("query"),
            "content_md": None,
            "toc": [],
            "summary": None,
            "quality_score": int(output.get("quality_score") or 0),
            "quality_feedback": output.get("quality_feedback"),
            "pass": bool(output.get("final")),
        },
        "next_action": "complete" if output.get("final") else "retry_organize",
        "metrics": {"finished_at": _now(), "token_usage": (output.get("token_usage") or {}).get("total", 0)},
        "metadata": {},
        "extensions": {},
    }
    return validate_agent_result(payload)


def _normalize_search_result(item: dict[str, Any]) -> dict[str, Any]:
    url = str(item.get("url") or item.get("source_site") or "about:blank")
    content = str(item.get("content") or item.get("snippet") or item.get("summary") or "No content")
    return {
        "title": str(item.get("title") or url or "Untitled")[:500],
        "url": url,
        "content": content,
        "source_site": item.get("source_site"),
        "provider": item.get("provider"),
        "score": item.get("score"),
        "fetched_at": item.get("fetched_at"),
        "metadata": item.get("metadata") or {},
    }
