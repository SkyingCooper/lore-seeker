from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import User, Topic, SearchTask
from worker.tasks import run_search_pipeline

router = APIRouter()


class TopicCreate(BaseModel):
    title: str
    keywords: List[str] = []
    description: str | None = None


class SearchRequest(BaseModel):
    query: str
    topic_id: str | None = None
    search_mode: str = "api"
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
    # 解析 topic：快速搜索自动创建临时主题
    if body.topic_id:
        topic = await db.get(Topic, int(body.topic_id))
        if not topic or topic.user_id != current_user.id:
            raise HTTPException(404, "Topic not found")
    else:
        topic = Topic(user_id=current_user.id, title=body.query, keywords=[body.query])
        db.add(topic)
        await db.commit()
        await db.refresh(topic)

    topic_config = {
        "search_mode": body.search_mode,
        "source_sites": body.source_sites,
        "keywords": topic.keywords,
        "description": topic.description,
    }

    task = SearchTask(
        user_id=current_user.id,
        topic_id=topic.id,
        query=body.query,
        source_sites=body.source_sites,
        search_mode=body.search_mode,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    run_search_pipeline.delay(str(task.id), str(current_user.id), body.query, topic_config)

    return {"task_id": str(task.id), "status": "pending"}


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    task = await db.get(SearchTask, int(task_id))
    if not task or task.user_id != current_user.id:
        from fastapi import HTTPException
        raise HTTPException(404, "Task not found")
    return {"task_id": str(task.id), "status": task.status}
