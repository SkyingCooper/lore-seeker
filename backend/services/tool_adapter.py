"""Tool contract adapter。

Agent 不直接调用搜索、爬虫等原始函数；本模块负责构造 tool.input / tool.output
envelope、校验 Tool 注册表 caller 权限，并返回业务代码需要的数据部分。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml

from constraint.validation.validator import ContractValidationError, validate_tool_input, validate_tool_output
from core.config import settings
from services.search_service import crawl_sites, search_api


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "constraint" / "tool_contracts" / "tool_registry.yaml"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _registry() -> dict[str, Any]:
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContractValidationError("tool.registry", "tool registry root must be an object")
    return data


def _tool_config(tool_name: str) -> dict[str, Any]:
    tools = (_registry().get("tools") or {})
    if tool_name not in tools:
        raise ContractValidationError("tool.registry", f"unknown tool: {tool_name}")
    tool = tools[tool_name]
    if not isinstance(tool, dict):
        raise ContractValidationError("tool.registry", f"tool config must be an object: {tool_name}")
    return tool


def _assert_allowed_caller(tool_name: str, caller: str) -> dict[str, Any]:
    tool = _tool_config(tool_name)
    if caller not in tool.get("allowed_callers", []):
        raise ContractValidationError("tool.registry", f"{caller} cannot call tool: {tool_name}")
    return tool


async def call_search_api_tool(
    *,
    caller: str,
    query: str,
    source_sites: list[str] | None = None,
    task_id: str | int | None = None,
    subtask_id: str | None = None,
) -> list[dict[str, Any]]:
    """按 tool.input/output contract 调用通用搜索 API。"""

    tool = _assert_allowed_caller("search_api", caller)
    provider = settings.SEARCH_API_PROVIDER
    limited_source_sites = (source_sites or [])[:5]
    envelope = {
        "schema_version": "1.0",
        "contract_type": "tool.input",
        "trace": {"trace_id": f"tool:search_api:{task_id or 'none'}", "task_id": task_id, "subtask_id": subtask_id},
        "tool_name": "search_api",
        "caller": caller,
        "input": {
            "kind": "search_api",
            "query": query,
            "source_sites": limited_source_sites,
            "provider": provider,
            "max_results": 10,
        },
        "timeout_seconds": int(tool.get("timeout_seconds") or 30),
        "retry": _retry_config(),
        "metadata": {},
    }
    validate_tool_input(envelope)
    return await _execute_tool(
        tool_name="search_api",
        trace=envelope["trace"],
        call=lambda: search_api(query, site_filter=limited_source_sites),
        data_key="results",
    )


async def call_crawler_tool(
    *,
    caller: str,
    urls: list[str],
    queries: list[str],
    task_id: str | int | None = None,
) -> list[dict[str, Any]]:
    """按 tool.input/output contract 调用爬虫。"""

    tool = _assert_allowed_caller("crawler", caller)
    envelope = {
        "schema_version": "1.0",
        "contract_type": "tool.input",
        "trace": {"trace_id": f"tool:crawler:{task_id or 'none'}", "task_id": task_id, "subtask_id": None},
        "tool_name": "crawler",
        "caller": caller,
        "input": {
            "kind": "crawler",
            "urls": urls[:5],
            "wait_until": "domcontentloaded",
            "max_chars": 3000,
            "user_agent": None,
        },
        "timeout_seconds": int(tool.get("timeout_seconds") or 60),
        "retry": _retry_config(),
        "metadata": {"query_count": len(queries)},
    }
    validate_tool_input(envelope)
    return await _execute_tool(
        tool_name="crawler",
        trace=envelope["trace"],
        call=lambda: crawl_sites(urls[:5], queries),
        data_key="pages",
    )


async def _execute_tool(
    *,
    tool_name: str,
    trace: dict[str, Any],
    call: Callable[[], Awaitable[list[dict[str, Any]]]],
    data_key: str,
) -> list[dict[str, Any]]:
    started = time.perf_counter()
    try:
        results = await call()
    except Exception as exc:
        output = {
            "schema_version": "1.0",
            "contract_type": "tool.output",
            "trace": trace,
            "tool_name": tool_name,
            "status": "failed",
            "data": {},
            "error": {
                "code": type(exc).__name__,
                "message": str(exc) or type(exc).__name__,
                "retryable": True,
                "category": "provider",
            },
            "metrics": {"duration_ms": _duration_ms(started), "retry_count": 0, "result_count": 0, "token_usage": None},
            "metadata": {},
        }
        validate_tool_output(output)
        raise

    output = {
        "schema_version": "1.0",
        "contract_type": "tool.output",
        "trace": trace,
        "tool_name": tool_name,
        "status": "succeeded",
        "data": {data_key: results},
        "error": None,
        "metrics": {
            "duration_ms": _duration_ms(started),
            "retry_count": 0,
            "result_count": len(results),
            "token_usage": None,
        },
        "metadata": {"finished_at": _now()},
    }
    validate_tool_output(output)
    return results


def _retry_config() -> dict[str, Any]:
    defaults = _registry().get("defaults") or {}
    retry = defaults.get("retry") or {}
    return {
        "max_attempts": int(retry.get("max_attempts") or 3),
        "backoff": retry.get("backoff") or "exponential",
    }


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
