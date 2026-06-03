from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import User, Topic, SearchTask
from services.task_service import create_task_bundle, start_task_bundle

router = APIRouter()


class TopicCreate(BaseModel):
    title: str
    keywords: List[str] = []
    description: str | None = None


class SearchRequest(BaseModel):
    query: str
    topic_id: str | None = None
    search_mode: str = "mixed"
    source_sites: List[str] = []


@router.get("/topics")
async def list_topics(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Topic).where(Topic.user_id == current_user.id))
    return [{"id": str(t.id), "title": t.title, "keywords": t.keywords, "description": t.description} for t in result.scalars()]


@router.post("/topics")
async def create_topic(body: TopicCreate, current_user: User = Depends(require_member), db: AsyncSession = Depends(get_db)):
    topic = Topic(user_id=current_user.id, **body.model_dump())
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return {"id": str(topic.id), "title": topic.title}


@router.post("/start")
async def start_search(
    body: SearchRequest,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    bundle = await create_task_bundle(
        db,
        user_id=current_user.id,
        query=body.query,
        topic_id=int(body.topic_id) if body.topic_id else None,
        topic_title=body.query,
        topic_keywords=[body.query],
        topic_description=None,
        source_sites=body.source_sites,
        search_mode=body.search_mode,
        frequency="once",
    )
    await start_task_bundle(db, bundle=bundle)
    await db.commit()
    await db.refresh(bundle.task)

    return {"task_id": str(bundle.task.id), "status": bundle.task.status}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = await db.get(SearchTask, int(task_id))
    if not task or task.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(404, "Task not found")
    return {"task_id": str(task.id), "status": task.status}
