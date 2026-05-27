"""搜索 Agent：API 优先 + 爬虫辅助，支持指定网站扫描。"""
from agents.graph import AgentState
from services.search_service import search_api, crawl_sites


async def searcher_node(state: AgentState) -> dict:
    config = state["topic_config"]
    plan = config.get("_plan", {})
    queries = plan.get("search_queries", [state["query"]])
    target_sites: list[str] = config.get("target_sites", [])
    search_mode: str = config.get("search_mode", "api")

    results = []

    if search_mode in ("api", "both"):
        for q in queries:
            hits = await search_api(q, site_filter=target_sites)
            results.extend(hits)

    if search_mode in ("crawl", "both") and target_sites:
        crawled = await crawl_sites(target_sites, queries)
        results.extend(crawled)

    # 去重（按 url）
    seen, deduped = set(), []
    for r in results:
        url = r.get("url", "")
        if url not in seen:
            seen.add(url)
            deduped.append(r)

    return {"raw_results": deduped}
