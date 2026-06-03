from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth import get_current_user, require_member
from core.database import get_db
from db.models import Topic, SearchTask, User
from services.task_service import create_task_bundle, start_existing_task

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    query: str | None = None
    topic_id: int | None = None
    topic_title: str | None = None
    topic_keywords: list[str] = []
    topic_description: str | None = None
    source_sites: list[str] = []
    search_mode: str = "mixed"
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
    bundle = await create_task_bundle(
        db,
        user_id=current_user.id,
        query=body.query,
        topic_id=body.topic_id,
        topic_title=body.topic_title,
        topic_keywords=body.topic_keywords,
        topic_description=body.topic_description,
        source_sites=body.source_sites,
        search_mode=body.search_mode,
        frequency=body.frequency,
    )
    await db.commit()
    await db.refresh(bundle.task)

    return {
        "id": bundle.task.id,
        "topic_id": bundle.task.topic_id,
        "query": bundle.task.query,
        "source_sites": bundle.task.source_sites,
        "search_mode": bundle.task.search_mode,
        "frequency": bundle.task.frequency,
        "status": bundle.task.status,
        "created_at": bundle.task.created_at.isoformat() if bundle.task.created_at else None,
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
            "query": t.query,
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
        "query": task.query,
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

    if task.frequency == "once":
        topic = await db.get(Topic, task.topic_id)
        await start_existing_task(db, task=task, topic=topic)
        await db.commit()
        return {"task_id": task.id, "status": task.status, "message": "One-off task submitted and started"}

    task.status = "pending"
    await db.commit()
    return {"task_id": task.id, "status": task.status, "message": "Periodic task submitted and will execute according to schedule"}


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

    topic = await db.get(Topic, task.topic_id)
    await start_existing_task(db, task=task, topic=topic)
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
