"""Retriever 对话记忆服务：Redis 预热、对话流水、偏好和语义记忆沉淀。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.embedding_router import get_embeddings
from db.models import EpisodicLog, SemanticMemory, UserPreference
from services.memory_manager import insert_episodic_log, insert_semantic_memory, upsert_user_preference

CONTEXT_TTL_SECONDS = 30 * 60


async def preload_retriever_context(db: AsyncSession, redis: Redis, *, user_id: int, session_id: str) -> dict[str, Any]:
    """首轮对话从 DB 预热情景记忆和语义记忆到 Redis；后续直接复用 Redis。"""

    context_key = _context_key(user_id, session_id)
    semantic_key = _semantic_key(user_id)

    context_raw = await redis.get(context_key)
    semantic_raw = await redis.get(semantic_key)
    if context_raw and semantic_raw:
        return {"episodic": json.loads(context_raw), "semantic": json.loads(semantic_raw)}

    episodic = await _load_episodic(db, user_id=user_id)
    semantic = await _load_semantic(db, user_id=user_id)
    await redis.setex(context_key, CONTEXT_TTL_SECONDS, json.dumps(episodic, ensure_ascii=False))
    await redis.setex(semantic_key, CONTEXT_TTL_SECONDS, json.dumps(semantic, ensure_ascii=False))
    return {"episodic": episodic, "semantic": semantic}


async def record_retriever_turn(
    db: AsyncSession,
    redis: Redis,
    *,
    user_id: int,
    session_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """每轮对话结束后记录情景记忆，并抽取简单偏好和长期事实。"""

    context_key = _context_key(user_id, session_id)
    now = datetime.utcnow().isoformat()
    turn = {
        "event_type": "conversation",
        "user_message": user_message,
        "assistant_message": assistant_message[:1000],
        "created_at": now,
    }
    raw = await redis.get(context_key)
    context = json.loads(raw) if raw else []
    context.append(turn)
    context = context[-5:]
    await redis.setex(context_key, CONTEXT_TTL_SECONDS, json.dumps(context, ensure_ascii=False))

    await insert_episodic_log(
        db,
        user_id=user_id,
        session_key=session_id,
        event_type="conversation",
        content=user_message,
        importance=_estimate_importance(user_message),
        metadata={"assistant_preview": assistant_message[:500]},
    )

    preference = _extract_preference(user_message)
    if preference:
        await upsert_user_preference(
            db,
            user_id=user_id,
            key=preference["key"],
            value=preference["value"],
            category="explicit",
            confidence=0.9,
        )

    fact = _extract_semantic_fact(user_message)
    if fact:
        embedding = (await get_embeddings([fact["summary"]]))[0]
        await insert_semantic_memory(
            db,
            user_id=user_id,
            title=fact["title"],
            summary=fact["summary"],
            content=fact["content"],
            embedding=embedding,
            confidence=0.75,
            source_type="conversation",
            source_id=None,
        )
        await redis.delete(_semantic_key(user_id))


async def _load_episodic(db: AsyncSession, *, user_id: int) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(EpisodicLog)
        .where(EpisodicLog.user_id == user_id, EpisodicLog.deleted_at.is_(None))
        .order_by(EpisodicLog.created_at.desc())
        .limit(5)
    )
    return [
        {
            "event_id": str(row.id),
            "event_type": row.event_type,
            "content": row.content,
            "importance": row.importance,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows.scalars()
    ]


async def _load_semantic(db: AsyncSession, *, user_id: int) -> list[dict[str, Any]]:
    rows = await db.execute(
        select(SemanticMemory)
        .where(
            SemanticMemory.deleted_at.is_(None),
            (SemanticMemory.user_id == user_id) | (SemanticMemory.user_id.is_(None)),
            SemanticMemory.confidence >= 0.6,
        )
        .order_by(SemanticMemory.confidence.desc(), SemanticMemory.last_accessed.desc().nullslast())
        .limit(50)
    )
    return [
        {
            "id": row.id,
            "title": row.title,
            "summary": row.summary,
            "confidence": row.confidence,
        }
        for row in rows.scalars()
    ]


def _extract_preference(text: str) -> dict[str, Any] | None:
    patterns = [
        (r"我喜欢(.{2,40})", "general_preference"),
        (r"我希望(.{2,40})", "response_preference"),
        (r"回答.*(简洁|详细|中文|英文)", "response_style"),
    ]
    for pattern, key in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1) if match.groups() else match.group(0)
            return {"key": key, "value": value.strip(" ，。,.")}
    return None


def _extract_semantic_fact(text: str) -> dict[str, str] | None:
    if not re.search(r"(我是|我在|我正在|我们正在|当前项目|我的项目)", text):
        return None
    content = text.strip()
    if len(content) < 6:
        return None
    summary = content[:150]
    return {"title": summary[:60], "summary": summary, "content": content}


def _estimate_importance(text: str) -> float:
    if re.search(r"(重要|记住|偏好|喜欢|讨厌|我是|我正在|项目)", text):
        return 0.8
    return 0.5


def _context_key(user_id: int, session_id: str) -> str:
    return f"session:{user_id}:{session_id}:context"


def _semantic_key(user_id: int) -> str:
    return f"user:{user_id}:semantic"
