"""Tool contract adapter。

Agent 不直接调用搜索、爬虫等原始函数；本模块负责构造 tool.input / tool.output
envelope、校验 Tool 注册表 caller 权限，并返回业务代码需要的数据部分。
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
import os
from typing import Any, Awaitable, Callable

import yaml

from constraint.validation.validator import ContractValidationError, validate_tool_input, validate_tool_output
from core.config import settings
from services.search_service import crawl_sites, search_api


REGISTRY_PATH = Path(__file__).resolve().parents[1] / "constraint" / "tool_contracts" / "tool_registry.yaml"
RUNTIME_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_mcp.yaml"
MCP_HANDLERS: dict[tuple[str, str], Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _registry() -> dict[str, Any]:
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContractValidationError("tool.registry", "tool registry root must be an object")
    return data


def _runtime_config() -> dict[str, Any]:
    with RUNTIME_CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ContractValidationError("tool.runtime", "tool runtime config root must be an object")
    return _resolve_env_placeholders(data)


def _resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_env_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(v) for v in value]
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return os.getenv(value[2:-1], "")
    return value


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


def discover_enabled_tools(*, owner_agent: str | None = None) -> list[dict[str, Any]]:
    """返回当前启用的 Tool / MCP 能力清单，供动态发现与审计使用。"""

    runtime = (_runtime_config().get("tool_mcp") or {})
    tools_registry = runtime.get("tools_registry") or {}
    items: list[dict[str, Any]] = []
    for name, item in tools_registry.items():
        if not isinstance(item, dict) or not item.get("enabled", False):
            continue
        if owner_agent and item.get("owner_agent") != owner_agent:
            continue
        items.append(
            {
                "name": name,
                "description": item.get("description", ""),
                "owner_agent": item.get("owner_agent"),
                "input_kind": item.get("input_kind"),
            }
        )
    if owner_agent:
        items.append(
            {
                "name": "mcp_gateway",
                "description": "Registered MCP gateway",
                "owner_agent": owner_agent,
                "input_kind": "mcp",
            }
        )
    return items


def list_registered_mcp_servers() -> list[dict[str, Any]]:
    runtime = ((_runtime_config().get("tool_mcp") or {}).get("mcp") or {})
    servers = runtime.get("servers") or []
    result: list[dict[str, Any]] = []
    for item in servers:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        result.append(
            {
                "name": item["name"],
                "enabled": bool(item.get("enabled", True)),
                "transport": item.get("transport"),
                "timeout_seconds": item.get("timeout_seconds", runtime.get("default_timeout_seconds", 30)),
                "allowed_tools": item.get("allowed_tools", []),
            }
        )
    return result


def register_mcp_handler(
    *,
    server: str,
    tool: str,
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
) -> None:
    """注册本地 MCP handler，便于测试和统一网关调用。"""

    MCP_HANDLERS[(server, tool)] = handler


async def call_search_api_tool(
    *,
    caller: str,
    query: str,
    source_sites: list[str] | None = None,
    task_id: str | int | None = None,
    subtask_id: str | None = None,
    include_metadata: bool = False,
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
        provider=provider,
        runtime_item=((_runtime_config().get("tool_mcp") or {}).get("search") or {}).get("web_search", {}),
        include_metadata=include_metadata,
    )


async def call_named_search_tool(
    *,
    tool_name: str,
    caller: str,
    query: str,
    source_sites: list[str] | None = None,
    task_id: str | int | None = None,
    subtask_id: str | None = None,
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
    """调用声明式搜索 Tool；当前 provider 层统一复用 search_api 实现。"""

    if tool_name not in {"web_search", "academic_search", "github_search", "stackoverflow_search", "news_search"}:
        raise ContractValidationError("tool.registry", f"unsupported search tool: {tool_name}")

    tool = _assert_allowed_caller(tool_name, caller)
    runtime_tools = ((_runtime_config().get("tool_mcp") or {}).get("tools_registry") or {})
    runtime_item = runtime_tools.get(tool_name) or {}
    if not runtime_item.get("enabled", False):
        raise ContractValidationError("tool.runtime", f"disabled tool: {tool_name}")

    provider = _provider_for_search_tool(tool_name)
    limited_source_sites = (source_sites or [])[:5]
    envelope = {
        "schema_version": "1.0",
        "contract_type": "tool.input",
        "trace": {"trace_id": f"tool:{tool_name}:{task_id or 'none'}", "task_id": task_id, "subtask_id": subtask_id},
        "tool_name": tool_name,
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
        "metadata": {"tool_alias": tool_name},
    }
    validate_tool_input(envelope)
    return await _execute_tool(
        tool_name=tool_name,
        trace=envelope["trace"],
        call=lambda: search_api(query, site_filter=limited_source_sites),
        data_key=_search_output_key(tool_name),
        provider=provider,
        runtime_item=((_runtime_config().get("tool_mcp") or {}).get("search") or {}).get(tool_name, {}),
        include_metadata=include_metadata,
    )


async def call_crawler_tool(
    *,
    caller: str,
    urls: list[str],
    queries: list[str],
    task_id: str | int | None = None,
    include_metadata: bool = False,
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
        provider="crawler",
        runtime_item=((_runtime_config().get("tool_mcp") or {}).get("crawler") or {}).get("http_crawler", {}),
        include_metadata=include_metadata,
    )


async def call_named_crawler_tool(
    *,
    tool_name: str,
    caller: str,
    urls: list[str],
    queries: list[str],
    task_id: str | int | None = None,
    include_metadata: bool = False,
) -> list[dict[str, Any]]:
    """调用声明式 crawler Tool；动态 crawler/anti_ban 通过配置和 metadata 区分策略。"""

    if tool_name not in {"http_crawler", "dynamic_crawler", "anti_ban"}:
        raise ContractValidationError("tool.registry", f"unsupported crawler tool: {tool_name}")
    _assert_allowed_caller(tool_name, caller)
    runtime_tools = ((_runtime_config().get("tool_mcp") or {}).get("tools_registry") or {})
    runtime_item = runtime_tools.get(tool_name) or {}
    if not runtime_item.get("enabled", False):
        raise ContractValidationError("tool.runtime", f"disabled tool: {tool_name}")
    return await _execute_tool(
        tool_name=tool_name,
        trace={"trace_id": f"tool:{tool_name}:{task_id or 'none'}", "task_id": task_id, "subtask_id": None},
        call=lambda: crawl_sites(urls[:5], queries),
        data_key="pages",
        provider=tool_name,
        runtime_item=((_runtime_config().get("tool_mcp") or {}).get("crawler") or {}).get(tool_name, {}),
        include_metadata=include_metadata,
    )


async def call_mcp_tool(
    *,
    caller: str,
    server: str,
    tool: str,
    arguments: dict[str, Any],
    task_id: str | int | None = None,
    subtask_id: str | None = None,
) -> dict[str, Any]:
    """统一 MCP gateway。只允许调用已注册 server/tool。"""

    _assert_allowed_caller("mcp_gateway", caller)
    server_config = _registered_mcp_server(server)
    allowed_tools = server_config.get("allowed_tools") or []
    if allowed_tools and tool not in allowed_tools:
        raise ContractValidationError("tool.runtime", f"tool {tool} is not allowed for MCP server {server}")

    envelope = {
        "schema_version": "1.0",
        "contract_type": "tool.input",
        "trace": {"trace_id": f"tool:mcp_gateway:{task_id or 'none'}", "task_id": task_id, "subtask_id": subtask_id},
        "tool_name": "mcp_gateway",
        "caller": caller,
        "input": {"kind": "mcp", "server": server, "tool": tool, "arguments": arguments},
        "timeout_seconds": int(server_config.get("timeout_seconds") or 30),
        "retry": _retry_config(),
        "metadata": {},
    }
    validate_tool_input(envelope)

    handler = MCP_HANDLERS.get((server, tool))
    if handler is None:
        raise ContractValidationError("tool.runtime", f"no local MCP handler registered for {server}:{tool}")

    started = time.perf_counter()
    result = await handler(arguments)
    output = {
        "schema_version": "1.0",
        "contract_type": "tool.output",
        "trace": envelope["trace"],
        "tool_name": "mcp_gateway",
        "status": "succeeded",
        "data": {"result": result, "server": server, "tool": tool},
        "error": None,
        "metrics": {"duration_ms": _duration_ms(started), "retry_count": 0, "result_count": 1, "token_usage": None},
        "metadata": {"finished_at": _now()},
    }
    validate_tool_output(output)
    return output["data"]


async def _execute_tool(
    *,
    tool_name: str,
    trace: dict[str, Any],
    call: Callable[[], Awaitable[list[dict[str, Any]]]],
    data_key: str,
    provider: str | None,
    runtime_item: dict[str, Any] | None,
    include_metadata: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
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
            "metadata": {
                "provider": provider,
                "cost_usage": _estimate_cost_usage(runtime_item or {}, provider=provider, result_count=0),
            },
        }
        validate_tool_output(output)
        raise

    cost_usage = _estimate_cost_usage(runtime_item or {}, provider=provider, result_count=len(results))
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
        "metadata": {"finished_at": _now(), "provider": provider, "cost_usage": cost_usage},
    }
    validate_tool_output(output)
    if include_metadata:
        return {"items": results, "tool_output": output}
    return results


def _retry_config() -> dict[str, Any]:
    defaults = _registry().get("defaults") or {}
    retry = defaults.get("retry") or {}
    return {
        "max_attempts": int(retry.get("max_attempts") or 3),
        "backoff": retry.get("backoff") or "exponential",
    }


def _provider_for_search_tool(tool_name: str) -> str:
    mapping = {
        "web_search": "google",
        "academic_search": "google_scholar",
        "github_search": "github",
        "stackoverflow_search": "stackexchange",
        "news_search": "newsapi",
    }
    return mapping[tool_name]


def _search_output_key(tool_name: str) -> str:
    return {
        "web_search": "results",
        "academic_search": "papers",
        "github_search": "items",
        "stackoverflow_search": "questions",
        "news_search": "articles",
    }[tool_name]


def _registered_mcp_server(name: str) -> dict[str, Any]:
    for item in list_registered_mcp_servers():
        if item["name"] == name:
            if not item.get("enabled", True):
                raise ContractValidationError("tool.runtime", f"disabled MCP server: {name}")
            return item
    raise ContractValidationError("tool.runtime", f"unregistered MCP server: {name}")


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _estimate_cost_usage(runtime_item: dict[str, Any], *, provider: str | None, result_count: int) -> dict[str, Any]:
    """按配置估算一次 Tool 调用的成本与额度消耗。

    这里记录的是统一估算账本，不承诺与 provider 最终账单逐毫分一致。真实账单对账后可再扩展。
    """

    cost_cfg = (runtime_item.get("cost") or {}) if isinstance(runtime_item, dict) else {}
    quota_cfg = (runtime_item.get("quota") or {}) if isinstance(runtime_item, dict) else {}
    base_cost = float(cost_cfg.get("base_request_cost_usd") or 0.0)
    per_result_cost = float(cost_cfg.get("per_result_cost_usd") or 0.0)
    per_page_cost = float(cost_cfg.get("per_page_cost_usd") or 0.0)
    estimated_cost = round(base_cost + (per_result_cost * result_count) + (per_page_cost * result_count), 6)
    request_count = int(cost_cfg.get("request_count_per_call") or 1)
    quota_consumed = int(quota_cfg.get("quota_per_call") or request_count)
    return {
        "provider": provider,
        "billing_mode": cost_cfg.get("billing_mode") or "estimated",
        "estimated_cost_usd": estimated_cost,
        "request_count": request_count,
        "quota_consumed": quota_consumed,
        "quota_unit": quota_cfg.get("unit") or "request",
        "result_count": int(result_count or 0),
    }
