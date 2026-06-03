"""任务服务：统一封装任务创建、快捷启动和周期任务启动逻辑。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SearchTask, Topic


VALID_SEARCH_MODES = {"api", "crawl", "mixed"}
VALID_FREQUENCIES = {"once", "daily", "weekly", "biweekly", "monthly"}


@dataclass(slots=True)
class TaskBundle:
    task: SearchTask
    topic: Topic


def _normalize_search_mode(search_mode: str) -> str:
    mode = (search_mode or "mixed").strip().lower()
    if mode not in VALID_SEARCH_MODES:
        raise HTTPException(400, detail={"code": "SEARCH_MODE_INVALID", "detail": f"Unsupported search_mode: {search_mode}"})
    return mode


def _normalize_frequency(frequency: str) -> str:
    value = (frequency or "once").strip().lower()
    if value not in VALID_FREQUENCIES:
        raise HTTPException(400, detail={"code": "FREQUENCY_INVALID", "detail": f"Unsupported frequency: {frequency}"})
    return value


def _derive_task_query(*, query: str | None, topic: Topic, topic_title: str | None = None) -> str:
    value = (query or "").strip()
    if value:
        return value
    fallback = (topic_title or topic.title or "").strip()
    return fallback or "untitled"


async def resolve_topic(
    db: AsyncSession,
    *,
    user_id: int,
    topic_id: int | None,
    topic_title: str | None,
    topic_keywords: list[str] | None,
    topic_description: str | None,
) -> Topic:
    """解析任务使用的主题；优先使用已有主题，否则创建新主题。"""

    if topic_id is not None:
        topic = await db.get(Topic, topic_id)
        if not topic or topic.user_id != user_id:
            raise HTTPException(404, "Topic not found")
        return topic

    title = (topic_title or "").strip()
    if not title:
        raise HTTPException(400, detail={"code": "TOPIC_REQUIRED", "detail": "Must provide topic_id or topic_title"})

    topic = Topic(
        user_id=user_id,
        title=title,
        keywords=topic_keywords or [],
        description=topic_description,
    )
    db.add(topic)
    await db.flush()
    return topic


async def create_task_bundle(
    db: AsyncSession,
    *,
    user_id: int,
    query: str | None,
    topic_id: int | None,
    topic_title: str | None,
    topic_keywords: list[str] | None,
    topic_description: str | None,
    source_sites: list[str] | None,
    search_mode: str,
    frequency: str,
) -> TaskBundle:
    """创建任务及其绑定主题。"""

    topic = await resolve_topic(
        db,
        user_id=user_id,
        topic_id=topic_id,
        topic_title=topic_title,
        topic_keywords=topic_keywords,
        topic_description=topic_description,
    )
    task = SearchTask(
        user_id=user_id,
        topic_id=topic.id,
        query=_derive_task_query(query=query, topic=topic, topic_title=topic_title),
        source_sites=source_sites or [],
        search_mode=_normalize_search_mode(search_mode),
        frequency=_normalize_frequency(frequency),
        status="pending",
    )
    db.add(task)
    await db.flush()
    return TaskBundle(task=task, topic=topic)


def build_topic_config(task: SearchTask, topic: Topic | None) -> dict:
    """生成投递给 worker 的稳定任务配置。"""

    return {
        "search_mode": task.search_mode,
        "source_sites": task.source_sites,
        "frequency": task.frequency,
        "keywords": topic.keywords if topic else [],
        "description": topic.description if topic else None,
    }


async def start_task_bundle(
    db: AsyncSession,
    *,
    bundle: TaskBundle,
) -> SearchTask:
    """立即启动一个任务。"""

    task = bundle.task
    if task.status in ("fetching", "organizing"):
        raise HTTPException(400, detail={"code": "TASK_RUNNING", "detail": "Task is already running"})

    _enqueue_task(task, bundle.topic)
    task.status = "fetching"
    await db.flush()
    return task


async def start_existing_task(
    db: AsyncSession,
    *,
    task: SearchTask,
    topic: Topic | None,
) -> SearchTask:
    """启动已存在任务。"""

    if task.status in ("fetching", "organizing"):
        raise HTTPException(400, detail={"code": "TASK_RUNNING", "detail": "Task is already running"})
    _enqueue_task(task, topic)
    task.status = "fetching"
    await db.flush()
    return task


def _enqueue_task(task: SearchTask, topic: Topic | None) -> None:
    from worker.tasks import run_search_pipeline

    task_config = build_topic_config(task, topic)
    run_search_pipeline.delay(str(task.id), str(task.user_id), task.query or (topic.title if topic else "untitled"), task_config)
