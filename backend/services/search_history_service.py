"""搜索历史服务：记录实际搜索来源、执行方式和原始结果。

Searcher 负责执行搜索，Worker 在任务收尾阶段调用本模块把最终 raw_results
落入 search_histories，并把生成的 history id 写回 knowledge_chunks.source_search_ids。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from constraint.validation.validator import validate_db_contract
from db.models import SearchHistory, SearchTask


async def create_search_history(
    db: AsyncSession,
    *,
    task: SearchTask,
    query: str,
    raw_results: list[dict[str, Any]],
    status: str = "completed",
    report_id: int | None = None,
    parent_id: int | None = None,
    retry_count: int = 0,
    execution_duration: int | None = None,
    failure_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SearchHistory:
    """创建一条搜索历史。

    `source_sites` 和 `search_mode` 记录本次任务实际执行结果，而不是只记录用户期望。
    """

    source_sites = _extract_actual_sources(raw_results, task.source_sites)
    search_mode = _actual_search_mode(raw_results, task.search_mode)
    validate_db_contract(
        "insert_search_history",
        caller="worker",
        operation="insert",
        payload={
            "user_id": task.user_id,
            "task_id": task.id,
            "topic_id": task.topic_id,
            "report_id": report_id,
            "parent_id": parent_id,
            "query": query,
            "source_sites": source_sites,
            "search_mode": search_mode,
            "status": status,
            "result_count": len(raw_results),
            "retry_count": retry_count,
            "execution_duration": execution_duration,
            "failure_reason": failure_reason,
            "raw_results": raw_results,
            "metadata": metadata or {},
        },
    )
    history = SearchHistory(
        parent_id=parent_id,
        user_id=task.user_id,
        task_id=task.id,
        topic_id=task.topic_id,
        report_id=report_id,
        query=query,
        source_sites=source_sites,
        search_mode=search_mode,
        status=status,
        result_count=len(raw_results),
        retry_count=retry_count,
        execution_duration=execution_duration,
        failure_reason=failure_reason,
        raw_results=raw_results,
        metadata_=metadata or {"archived_at": datetime.utcnow().isoformat()},
    )
    db.add(history)
    await db.flush()
    return history


def attach_report(history: SearchHistory, report_id: int) -> None:
    """把先于报告创建的 search_history 关联到报告。"""

    history.report_id = report_id


def _extract_actual_sources(raw_results: list[dict[str, Any]], fallback: list | None) -> list[str]:
    sources: list[str] = []
    for item in raw_results:
        source = item.get("source") or item.get("site") or item.get("domain")
        if not source and item.get("url"):
            source = _domain_from_url(str(item["url"]))
        if source and source not in sources:
            sources.append(str(source))
    return sources or [str(item) for item in (fallback or [])]


def _actual_search_mode(raw_results: list[dict[str, Any]], fallback: str) -> str:
    modes = {str(item.get("search_mode") or item.get("kind") or "") for item in raw_results}
    has_api = any(mode in {"api", "search_api", "web_search"} for mode in modes)
    has_crawl = any(mode in {"crawl", "crawler", "http_crawler"} for mode in modes)
    if has_api and has_crawl:
        return "mixed"
    if has_crawl:
        return "crawl"
    if has_api:
        return "api"
    return fallback or "mixed"


def _domain_from_url(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.netloc or url
