"""搜索 Agent：API 优先 + 爬虫辅助，支持指定网站扫描。"""
from agents.graph import AgentState
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
from services.search_service import search_api, crawl_sites


async def searcher_node(state: AgentState) -> dict:
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
    search_mode: str = config.get("search_mode", "api")

    results = []

    if search_mode in ("api", "mixed"):
        for q in queries:
            before_tool_call(
                ToolCallContext(
                    agent_name="searcher",
                    tool_name="search_api",
                    operation="execute_search_api",
                    args={"query": q, "source_sites": source_sites},
                )
            )
            try:
                hits = await search_api(q, site_filter=source_sites)
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
                    tool_name="search_api",
                    operation="execute_search_api",
                    result={"count": len(hits)},
                )
            )
            results.extend(hits)

    if search_mode in ("crawl", "mixed") and source_sites:
        before_tool_call(
            ToolCallContext(
                agent_name="searcher",
                tool_name="crawler",
                operation="crawl_source_sites",
                args={"source_sites": source_sites, "queries": queries},
            )
        )
        try:
            crawled = await crawl_sites(source_sites, queries)
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

    output = {"raw_results": deduped}
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
