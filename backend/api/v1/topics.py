"""主题接口：统一管理用户主题。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.v1.auth import get_current_user, require_member
from core.database import get_db
from db.models import Topic, User

router = APIRouter()


class TopicCreate(BaseModel):
    title: str
    keywords: list[str] = []
    description: str | None = None


@router.get("")
async def list_topics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Topic).where(Topic.user_id == current_user.id))
    return [
        {
            "id": str(topic.id),
            "title": topic.title,
            "keywords": topic.keywords,
            "description": topic.description,
        }
        for topic in result.scalars()
    ]


@router.post("")
async def create_topic(
    body: TopicCreate,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    topic = Topic(user_id=current_user.id, **body.model_dump())
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return {"id": str(topic.id), "title": topic.title}
