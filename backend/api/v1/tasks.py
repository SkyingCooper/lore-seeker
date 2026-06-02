from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import Topic, SearchTask, User

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    topic_id: int | None = None
    topic_title: str | None = None
    topic_keywords: list[str] = []
    topic_description: str | None = None
    source_sites: list[str] = []
    search_mode: str = "api"
    frequency: str = "once"


class TaskUpdate(BaseModel):
    topic_id: int | None = None
    source_sites: list[str] | None = None
    search_mode: str | None = None
    frequency: str | None = None


# ─── Endpoints ────────────────────────────────────────────────────────────

@router.post("")
async def create_task(
    body: TaskCreate,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    # 解析主题：优先用已有 topic_id，否则自动创建
    topic_id = body.topic_id
    if topic_id is None:
        if not body.topic_title:
            raise HTTPException(400, detail={"code": "TOPIC_REQUIRED", "detail": "Must provide topic_id or topic_title"})
        topic = Topic(
            user_id=current_user.id,
            title=body.topic_title,
            keywords=body.topic_keywords,
            description=body.topic_description,
        )
        db.add(topic)
        await db.commit()
        await db.refresh(topic)
        topic_id = topic.id
    else:
        topic = await db.get(Topic, topic_id)
        if not topic or topic.user_id != current_user.id:
            raise HTTPException(404, "Topic not found")

    task = SearchTask(
        user_id=current_user.id,
        topic_id=topic_id,
        source_sites=body.source_sites,
        search_mode=body.search_mode,
        frequency=body.frequency,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return {
        "id": task.id,
        "topic_id": task.topic_id,
        "source_sites": task.source_sites,
        "search_mode": task.search_mode,
        "frequency": task.frequency,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.get("")
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SearchTask, Topic.title)
        .join(Topic, SearchTask.topic_id == Topic.id)
        .where(SearchTask.user_id == current_user.id, SearchTask.deleted_at.is_(None))
        .order_by(SearchTask.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": t.id,
            "topic_id": t.topic_id,
            "topic_title": topic_title,
            "source_sites": t.source_sites,
            "search_mode": t.search_mode,
            "frequency": t.frequency,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t, topic_title in rows
    ]


@router.get("/{task_id}")
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(SearchTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")

    # 同时加载关联的主题信息
    topic = await db.get(Topic, task.topic_id)

    return {
        "id": task.id,
        "topic_id": task.topic_id,
        "topic": {
            "id": topic.id,
            "title": topic.title,
            "keywords": topic.keywords,
            "description": topic.description,
        } if topic else None,
        "source_sites": task.source_sites,
        "search_mode": task.search_mode,
        "frequency": task.frequency,
        "status": task.status,
        "deleted_at": task.deleted_at.isoformat() if task.deleted_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.post("/{task_id}/submit")
async def submit_task(
    task_id: int,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(SearchTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")

    if task.status not in ("pending", "failed"):
        raise HTTPException(400, detail={"code": "TASK_STATUS_INVALID", "detail": "Task is already running or completed"})

    task.status = "pending"
    await db.commit()

    # 如果是周期性任务，Celery Beat 会在下次调度时自动触发
    return {"task_id": task.id, "status": task.status, "message": "Task submitted, will execute according to schedule"}


@router.post("/{task_id}/start")
async def start_task(
    task_id: int,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(SearchTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")

    if task.status in ("fetching", "organizing"):
        raise HTTPException(400, detail={"code": "TASK_RUNNING", "detail": "Task is already running"})

    # 触发执行
    from worker.tasks import run_search_pipeline
    topic = await db.get(Topic, task.topic_id)

    task_config = {
        "search_mode": task.search_mode,
        "source_sites": task.source_sites,
        "keywords": topic.keywords if topic else [],
        "description": topic.description if topic else None,
    }

    run_search_pipeline.delay(str(task.id), str(current_user.id), topic.title if topic else "untitled", task_config)
    task.status = "fetching"
    await db.commit()

    return {"task_id": task.id, "status": "fetching", "message": "Task started"}


@router.post("/{task_id}/retry")
async def retry_task(
    task_id: int,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(SearchTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")

    if task.status != "failed":
        raise HTTPException(400, detail={"code": "TASK_NOT_FAILED", "detail": "Only failed tasks can be retried"})

    task.status = "pending"
    await db.commit()

    return {"task_id": task.id, "status": "pending", "message": "Task queued for retry"}


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    task = await db.get(SearchTask, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(404, "Task not found")

    task.deleted_at = datetime.utcnow()
    await db.commit()

    return {"task_id": task.id, "deleted_at": task.deleted_at.isoformat()}
