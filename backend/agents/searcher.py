"""搜索 Agent：API 优先 + 爬虫辅助，支持指定网站扫描。"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from agents.graph import AgentState
from agents.contracts import validate_searcher_result
from agents.guardrails import (
    AgentErrorContext,
    AgentOutputContext,
    AgentRunContext,
    ToolCallContext,
    ToolResultContext,
    after_run,
    after_tool_call,
    before_run,
    before_tool_call,
    on_error,
    on_tool_error,
)
from services.tool_adapter import call_crawler_tool, call_named_search_tool
from agents.token_usage import merge_stage_usage

SEARCHER_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "searcher.yaml"
TOOL_MCP_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "tool_mcp.yaml"


async def run_searcher_agent(state: AgentState) -> dict:
    before_run(
        AgentRunContext(
            agent_name="searcher",
            responsibility="search_api_execution",
            operation="execute_search_api",
            user_id=state.get("user_id"),
            task_id=state.get("task_id"),
            state=dict(state),
        )
    )
    config = state["topic_config"]
    plan = config.get("_plan", {})
    queries = plan.get("search_queries", [state["query"]])
    source_sites: list[str] = config.get("source_sites", [])
    search_mode: str = config.get("search_mode", "mixed")
    token_usage = merge_stage_usage(
        state.get("token_usage"),
        stage="search",
        usage={"input_tokens": 0, "output_tokens": 0, "total": 0},
        model=None,
    )

    results = []
    retry_cfg = _searcher_config().get("retry", {})

    if search_mode in ("api", "mixed"):
        for q in queries:
            selected_tool = _select_search_tool(q)
            before_tool_call(
                ToolCallContext(
                    agent_name="searcher",
                    tool_name=selected_tool,
                    operation="execute_search_api",
                    args={"query": q, "source_sites": source_sites, "selected_tool": selected_tool},
                )
            )
            try:
                hits = await _execute_with_retry(
                    lambda: call_named_search_tool(
                        tool_name=selected_tool,
                        caller="searcher",
                        query=q,
                        source_sites=source_sites,
                        task_id=state.get("task_id"),
                    ),
                    max_attempts=int(retry_cfg.get("max_attempts", 3)),
                    initial_delay=float(retry_cfg.get("initial_delay_seconds", 1)),
                    max_delay=float(retry_cfg.get("max_delay_seconds", 8)),
                    multiplier=float(retry_cfg.get("multiplier", 2)),
                )
            except Exception as exc:
                on_tool_error(
                    AgentErrorContext(
                        agent_name="searcher",
                        stage="on_tool_error",
                        operation="execute_search_api",
                        error_type=type(exc).__name__,
                        message=str(exc),
                        retryable=True,
                    )
                )
                raise
            after_tool_call(
                ToolResultContext(
                    agent_name="searcher",
                    tool_name=selected_tool,
                    operation="execute_search_api",
                    result={"count": len(hits)},
                )
            )
            results.extend(hits)

    if search_mode in ("crawl", "mixed") and source_sites:
        crawl_sites = _apply_site_limits(source_sites)
        before_tool_call(
            ToolCallContext(
                agent_name="searcher",
                tool_name="crawler",
                operation="crawl_source_sites",
                args={"source_sites": crawl_sites, "queries": queries},
            )
        )
        try:
            crawled = await _execute_with_retry(
                lambda: call_crawler_tool(
                    caller="searcher",
                    urls=crawl_sites,
                    queries=queries,
                    task_id=state.get("task_id"),
                ),
                max_attempts=int(retry_cfg.get("max_attempts", 3)),
                initial_delay=float(retry_cfg.get("initial_delay_seconds", 1)),
                max_delay=float(retry_cfg.get("max_delay_seconds", 8)),
                multiplier=float(retry_cfg.get("multiplier", 2)),
            )
        except Exception as exc:
            on_tool_error(
                AgentErrorContext(
                    agent_name="searcher",
                    stage="on_tool_error",
                    operation="crawl_source_sites",
                    error_type=type(exc).__name__,
                    message=str(exc),
                    retryable=True,
                )
            )
            raise
        after_tool_call(
            ToolResultContext(
                agent_name="searcher",
                tool_name="crawler",
                operation="crawl_source_sites",
                result={"count": len(crawled)},
            )
        )
        results.extend(crawled)

    # 去重（按 url）
    seen, deduped = set(), []
    for r in results:
        url = r.get("url", "")
        if url not in seen:
            seen.add(url)
            deduped.append(r)

    validate_searcher_result(state, deduped)
    output = {"raw_results": deduped, "token_usage": token_usage}
    try:
        after_run(AgentOutputContext(agent_name="searcher", operation="standardize_search_result", result=output))
    except Exception as exc:
        on_error(
            AgentErrorContext(
                agent_name="searcher",
                stage="on_error",
                operation="standardize_search_result",
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=False,
            )
        )
        raise
    return output


async def searcher_node(state: AgentState) -> dict:
    return await run_searcher_agent(state)


def _searcher_config() -> dict[str, Any]:
    default = {
        "retry": {"max_attempts": 3, "initial_delay_seconds": 1, "max_delay_seconds": 8, "multiplier": 2},
        "strategy": {"default_search_tool": "web_search", "query_tool_rules": []},
        "site_policy": {"fallback_concurrency_limit": 2, "fallback_request_delay_ms": 1000},
    }
    if not SEARCHER_CONFIG_PATH.exists():
        return default
    with SEARCHER_CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = (yaml.safe_load(f) or {}).get("searcher", {})
    return {**default, **data}


def _tool_mcp_config() -> dict[str, Any]:
    if not TOOL_MCP_CONFIG_PATH.exists():
        return {}
    with TOOL_MCP_CONFIG_PATH.open("r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("tool_mcp", {})


def _select_search_tool(query: str) -> str:
    cfg = _searcher_config().get("strategy", {})
    lowered = query.lower()
    for rule in cfg.get("query_tool_rules", []):
        terms = [str(item).lower() for item in rule.get("match_any", [])]
        if any(term and term in lowered for term in terms):
            return str(rule.get("tool") or cfg.get("default_search_tool", "web_search"))
    return str(cfg.get("default_search_tool", "web_search"))


def _apply_site_limits(source_sites: list[str]) -> list[str]:
    if not source_sites:
        return []
    tool_cfg = _tool_mcp_config().get("crawler", {})
    site_policies = tool_cfg.get("site_policies", {})
    fallback_limit = int(_searcher_config().get("concurrency", {}).get("global_max", 10))
    trimmed = source_sites[:fallback_limit]
    # 当前执行层先根据注册域名顺序裁剪；更细的每站点并发/延迟由 tool 层 provider 执行。
    prioritized = sorted(trimmed, key=lambda site: 0 if _domain(site) in site_policies else 1)
    return prioritized


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).netloc or url).lower()


async def _execute_with_retry(
    func,
    *,
    max_attempts: int,
    initial_delay: float,
    max_delay: float,
    multiplier: float,
):
    delay = max(initial_delay, 0)
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except Exception as exc:  # noqa: PERF203
            last_exc = exc
            if attempt >= max_attempts or not _is_retryable(exc):
                raise
            await asyncio.sleep(delay)
            delay = min(max_delay, max(delay * multiplier, initial_delay))
    if last_exc:
        raise last_exc
    raise RuntimeError("retry executor reached an impossible state")


def _is_retryable(exc: Exception) -> bool:
    lowered = str(exc).lower()
    retryable_markers = ("timeout", "tempor", "rate", "429", "502", "503", "504", "connection")
    return any(marker in lowered for marker in retryable_markers)
