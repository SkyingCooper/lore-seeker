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
from core.redis_client import get_redis
from core.task_redis import append_log, append_raw_results, set_subtasks, update_subtask
from services.tool_adapter import call_crawler_tool, call_named_search_tool
from agents.token_usage import merge_stage_usage
from agents.cost_usage import merge_stage_cost

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
    task_id = int(state.get("task_id") or 0)
    token_usage = merge_stage_usage(
        state.get("token_usage"),
        stage="search",
        usage={"input_tokens": 0, "output_tokens": 0, "total": 0},
        model=None,
    )
    cost_usage = state.get("cost_usage") or {}

    results = []
    retry_cfg = _searcher_config().get("retry", {})
    redis = await get_redis()
    jobs = _build_jobs(queries=queries, source_sites=source_sites, search_mode=search_mode)
    if task_id:
        await set_subtasks(redis, task_id, [job["subtask"] for job in jobs])
        await append_log(
            redis,
            task_id,
            "searcher",
            "搜索子任务已生成",
            interaction_type="state_update",
            status="running",
            payload={"job_count": len(jobs), "search_mode": search_mode},
        )

    execution_results = await _run_jobs(
        jobs,
        retry_cfg=retry_cfg,
        task_id=task_id,
        redis=redis,
    )
    for item in execution_results:
        results.extend(item["hits"])
        cost_usage = _merge_search_cost(cost_usage, item.get("cost_usage"))
    if _needs_search_fallback(results, state["query"]):
        fallback = await _run_search_fallback(
            query=state["query"],
            task_id=task_id,
            redis=redis,
            retry_cfg=retry_cfg,
        )
        results.extend(fallback["hits"])
        cost_usage = _merge_search_cost(cost_usage, fallback.get("cost_usage"))
    repair_results = await _run_quality_repair(
        query=state["query"],
        results=results,
        source_sites=source_sites,
        task_id=task_id,
        redis=redis,
        retry_cfg=retry_cfg,
    )
    if repair_results:
        results.extend(repair_results["hits"])
        cost_usage = _merge_search_cost(cost_usage, repair_results.get("cost_usage"))
    if task_id and results:
        await append_raw_results(redis, task_id, results)
        await append_log(
            redis,
            task_id,
            "searcher",
            "搜索结果已汇总写入 Redis",
            interaction_type="tool_result",
            status="running",
            payload={"result_count": len(results)},
        )

    # 去重（按 url）
    seen, deduped = set(), []
    for r in results:
        url = r.get("url", "")
        if url not in seen:
            seen.add(url)
            deduped.append(r)

    validate_searcher_result(state, deduped)
    output = {"raw_results": deduped, "token_usage": token_usage, "cost_usage": cost_usage}
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


def _build_jobs(*, queries: list[str], source_sites: list[str], search_mode: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    job_index = 0
    sites = _apply_site_limits(source_sites)

    if search_mode in ("api", "mixed"):
        for query in queries:
            selected_tool = _select_search_tool(query)
            if sites:
                for site in sites:
                    selected_tool = _site_override_tool(site) or _select_search_tool(query)
                    jobs.append(
                        {
                            "kind": "api",
                            "query": query,
                            "tool": selected_tool,
                            "site": site,
                            "subtask": _build_subtask(f"api-{job_index}", query, selected_tool, site),
                        }
                    )
                    job_index += 1
            else:
                jobs.append(
                    {
                        "kind": "api",
                        "query": query,
                        "tool": selected_tool,
                        "site": None,
                        "subtask": _build_subtask(f"api-{job_index}", query, selected_tool, None),
                    }
                )
                job_index += 1

    if search_mode in ("crawl", "mixed") and sites:
        for query in queries:
            for site in sites:
                site_override_tool = _site_override_tool(site)
                if site_override_tool:
                    jobs.append(
                        {
                            "kind": "api",
                            "query": query,
                            "tool": site_override_tool,
                            "site": site,
                            "subtask": _build_subtask(f"api-{job_index}", query, site_override_tool, site),
                        }
                    )
                    job_index += 1
                    continue
                jobs.append(
                    {
                        "kind": "crawl",
                        "query": query,
                        "tool": "crawler",
                        "site": site,
                        "subtask": _build_subtask(f"crawl-{job_index}", query, "crawler", site),
                    }
                )
                job_index += 1
    return jobs


def _build_subtask(subtask_id: str, query: str, tool: str, site: str | None) -> dict[str, Any]:
    return {
        "id": subtask_id,
        "subtask_id": subtask_id,
        "query": query,
        "tool": tool,
        "site": site,
        "status": "pending",
    }


async def _run_jobs(
    jobs: list[dict[str, Any]],
    *,
    retry_cfg: dict[str, Any],
    task_id: int,
    redis,
) -> list[dict[str, Any]]:
    global_limit = int(_searcher_config().get("concurrency", {}).get("global_max", 10))
    global_sem = asyncio.Semaphore(global_limit)
    site_sems: dict[str, asyncio.Semaphore] = {}

    async def execute(job: dict[str, Any]) -> dict[str, Any]:
        site = job.get("site")
        domain = _domain(site or "global")
        site_limit = _site_policy(domain).get("concurrency_limit", _searcher_config().get("site_policy", {}).get("fallback_concurrency_limit", 2))
        site_sem = site_sems.setdefault(domain, asyncio.Semaphore(int(site_limit)))
        async with global_sem, site_sem:
            return await _run_single_job(job, retry_cfg=retry_cfg, task_id=task_id, redis=redis)

    return await asyncio.gather(*(execute(job) for job in jobs))


async def _run_single_job(job: dict[str, Any], *, retry_cfg: dict[str, Any], task_id: int, redis) -> dict[str, Any]:
    subtask = job["subtask"]
    if task_id:
        await update_subtask(redis, task_id, subtask["id"], status="running")
        await append_log(
            redis,
            task_id,
            "searcher",
            f"开始执行子任务 {subtask['id']}",
            interaction_type="tool_call",
            status="running",
            tool_name=job["tool"],
            payload={"query": job["query"], "site": job.get("site")},
        )
    policy = _site_policy(_domain(job.get("site") or ""))
    delay_ms = int(policy.get("request_delay_ms", _searcher_config().get("site_policy", {}).get("fallback_request_delay_ms", 1000)))
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)

    operation = "execute_search_api" if job["kind"] == "api" else "crawl_source_sites"
    tool_name = job["tool"]
    before_tool_call(
        ToolCallContext(
            agent_name="searcher",
            tool_name=tool_name,
            operation=operation,
            args={"query": job["query"], "site": job.get("site")},
        )
    )
    try:
        if job["kind"] == "api":
            hits = await _execute_with_retry(
                lambda: call_named_search_tool(
                    tool_name=job["tool"],
                    caller="searcher",
                    query=job["query"],
                    source_sites=[job["site"]] if job.get("site") else [],
                    task_id=str(task_id) if task_id else None,
                    subtask_id=subtask["id"],
                    include_metadata=True,
                ),
                max_attempts=int(retry_cfg.get("max_attempts", 3)),
                initial_delay=float(retry_cfg.get("initial_delay_seconds", 1)),
                max_delay=float(retry_cfg.get("max_delay_seconds", 8)),
                multiplier=float(retry_cfg.get("multiplier", 2)),
            )
        else:
            hits = await _execute_with_retry(
                lambda: call_crawler_tool(
                    caller="searcher",
                    urls=[job["site"]],
                    queries=[job["query"]],
                    task_id=str(task_id) if task_id else None,
                    include_metadata=True,
                ),
                max_attempts=int(retry_cfg.get("max_attempts", 3)),
                initial_delay=float(retry_cfg.get("initial_delay_seconds", 1)),
                max_delay=float(retry_cfg.get("max_delay_seconds", 8)),
                multiplier=float(retry_cfg.get("multiplier", 2)),
            )
    except Exception as exc:
        if task_id:
            await update_subtask(redis, task_id, subtask["id"], status="failed", error_type=type(exc).__name__, error_message=str(exc))
            await append_log(
                redis,
                task_id,
                "searcher",
                f"子任务 {subtask['id']} 执行失败",
                interaction_type="error",
                status="failed",
                tool_name=tool_name,
                payload={"error_type": type(exc).__name__, "message": str(exc)},
            )
        on_tool_error(
            AgentErrorContext(
                agent_name="searcher",
                stage="on_tool_error",
                operation=operation,
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=_is_retryable(exc),
            )
        )
        raise

    after_tool_call(
        ToolResultContext(
            agent_name="searcher",
            tool_name=tool_name,
            operation=operation,
            result={"count": len(hits.get("items", [])) if isinstance(hits, dict) else len(hits)},
        )
    )
    if task_id:
        await update_subtask(
            redis,
            task_id,
            subtask["id"],
            status="done",
            result_count=len(hits.get("items", [])) if isinstance(hits, dict) else len(hits),
        )
    if isinstance(hits, dict):
        return {"hits": hits.get("items", []), "cost_usage": ((hits.get("tool_output") or {}).get("metadata") or {}).get("cost_usage")}
    return {"hits": hits, "cost_usage": None}


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


def _site_override_tool(site: str) -> str | None:
    capability = ((_tool_mcp_config().get("crawler", {}) or {}).get("source_capabilities") or {}).get(_domain(site), {})
    tool_name = capability.get("api_tool")
    if not tool_name:
        return None
    runtime_tools = (_tool_mcp_config().get("tools_registry") or {})
    if isinstance(runtime_tools, dict) and runtime_tools.get(tool_name, {}).get("enabled", False):
        return str(tool_name)
    return None


def _site_policy(domain: str) -> dict[str, Any]:
    site_policies = (_tool_mcp_config().get("crawler", {}) or {}).get("site_policies", {})
    return site_policies.get(domain, site_policies.get("default", {}))


def _needs_search_fallback(results: list[dict[str, Any]], query: str) -> bool:
    quality = _searcher_config().get("quality", {})
    low_result_threshold = int(quality.get("low_result_threshold", 3))
    low_relevance_threshold = float(quality.get("low_relevance_threshold", 0.3))
    if len(results) < low_result_threshold:
        return True
    if not results:
        return True
    scores = [_query_overlap_score(query, item) for item in results[:5]]
    average = sum(scores) / max(1, len(scores))
    return average < low_relevance_threshold


async def _run_search_fallback(*, query: str, task_id: int, redis, retry_cfg: dict[str, Any]) -> dict[str, Any]:
    if task_id:
        await append_log(
            redis,
            task_id,
            "searcher",
            "搜索结果不足，触发自动补搜策略",
            interaction_type="state_update",
            status="running",
            payload={"query": query, "fallback_tool": "web_search"},
        )
    result = await _execute_with_retry(
        lambda: call_named_search_tool(
            tool_name="web_search",
            caller="searcher",
            query=query,
            source_sites=[],
            task_id=str(task_id) if task_id else None,
            subtask_id="fallback-web-search",
            include_metadata=True,
        ),
        max_attempts=int(retry_cfg.get("max_attempts", 3)),
        initial_delay=float(retry_cfg.get("initial_delay_seconds", 1)),
        max_delay=float(retry_cfg.get("max_delay_seconds", 8)),
        multiplier=float(retry_cfg.get("multiplier", 2)),
    )
    return {
        "hits": result.get("items", []) if isinstance(result, dict) else result,
        "cost_usage": ((result.get("tool_output") or {}).get("metadata") or {}).get("cost_usage") if isinstance(result, dict) else None,
    }


async def _run_quality_repair(
    *,
    query: str,
    results: list[dict[str, Any]],
    source_sites: list[str],
    task_id: int,
    redis,
    retry_cfg: dict[str, Any],
) -> dict[str, Any] | None:
    tool = _choose_repair_tool(query, results)
    if not tool:
        return None
    if task_id:
        await append_log(
            redis,
            task_id,
            "searcher",
            "搜索质量评估后触发策略修复",
            interaction_type="state_update",
            status="running",
            payload={"query": query, "repair_tool": tool},
        )
    result = await _execute_with_retry(
        lambda: call_named_search_tool(
            tool_name=tool,
            caller="searcher",
            query=query,
            source_sites=source_sites[:3],
            task_id=str(task_id) if task_id else None,
            subtask_id=f"repair-{tool}",
            include_metadata=True,
        ),
        max_attempts=int(retry_cfg.get("max_attempts", 3)),
        initial_delay=float(retry_cfg.get("initial_delay_seconds", 1)),
        max_delay=float(retry_cfg.get("max_delay_seconds", 8)),
        multiplier=float(retry_cfg.get("multiplier", 2)),
    )
    return {
        "hits": result.get("items", []) if isinstance(result, dict) else result,
        "cost_usage": ((result.get("tool_output") or {}).get("metadata") or {}).get("cost_usage") if isinstance(result, dict) else None,
    }


def _query_overlap_score(query: str, item: dict[str, Any]) -> float:
    query_terms = _tokenize(query)
    content_terms = _tokenize(f"{item.get('title', '')} {item.get('content', '')}")
    if not query_terms or not content_terms:
        return 0.0
    return len(query_terms & content_terms) / max(1, len(query_terms))


def _tokenize(text: str) -> set[str]:
    import re

    return set(re.findall(r"[\w\u4e00-\u9fff]+", text.lower()))


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return (urlparse(url).netloc or url).lower()


def _choose_repair_tool(query: str, results: list[dict[str, Any]]) -> str | None:
    lowered = query.lower()
    domains = {_domain(str(item.get("url") or item.get("source") or "")) for item in results[:10]}
    if any(term in lowered for term in ("github", "repo", "repository", "issue", "pull request", "源码", "代码")):
        return None if any("github.com" in domain for domain in domains) else "github_search"
    if any(term in lowered for term in ("paper", "arxiv", "doi", "论文", "专利", "citation")):
        return "academic_search"
    if any(term in lowered for term in ("today", "latest", "breaking", "news", "今天", "最新", "新闻")):
        return "news_search"
    return None


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


def _merge_search_cost(current: dict[str, Any], item: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(item, dict):
        return current
    return merge_stage_cost(
        current,
        stage="search",
        provider=item.get("provider"),
        estimated_cost_usd=float(item.get("estimated_cost_usd") or 0.0),
        request_count=int(item.get("request_count") or 0),
        quota_consumed=int(item.get("quota_consumed") or 0),
        quota_unit=item.get("quota_unit"),
    )
