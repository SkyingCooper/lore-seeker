"""用户偏好服务：集中处理偏好读取、更新和撤销。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from constraint.validation.validator import validate_db_contract
from db.models import UserPreference


async def list_user_preferences(db: AsyncSession, *, user_id: int) -> list[UserPreference]:
    """读取用户全部偏好。"""

    validate_db_contract(
        "list_user_preferences",
        caller="api",
        operation="select",
        params={"user_id": user_id},
    )
    rows = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id).order_by(UserPreference.updated_at.desc())
    )
    return list(rows.scalars())


async def load_preferences_dict(db: AsyncSession, *, user_id: int) -> dict[str, Any]:
    """以 key-value 形式返回用户偏好。"""

    rows = await list_user_preferences(db, user_id=user_id)
    return {row.key: row.value for row in rows}


async def upsert_user_preference(
    db: AsyncSession,
    *,
    user_id: int,
    key: str,
    value: Any,
    category: str = "explicit",
    confidence: float | None = None,
) -> UserPreference:
    """写入或更新单个用户偏好。"""

    validate_db_contract(
        "upsert_user_preference",
        caller="api",
        operation="insert_or_update",
        payload={"user_id": user_id, "key": key, "value": value, "category": category},
    )
    existing = await db.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.key == key,
        )
    )
    if existing:
        existing.value = value
        existing.category = category
        existing.confidence = confidence
        existing.updated_at = datetime.utcnow()
        return existing

    preference = UserPreference(
        user_id=user_id,
        key=key,
        value=value,
        category=category,
        confidence=confidence,
    )
    db.add(preference)
    return preference


async def delete_user_preference(db: AsyncSession, *, user_id: int, key: str) -> int:
    """删除单个偏好，作为用户主动撤销。"""

    validate_db_contract(
        "delete_user_preference",
        caller="api",
        operation="delete",
        payload={"user_id": user_id, "key": key},
    )
    result = await db.execute(
        delete(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.key == key,
        )
    )
    return int(result.rowcount or 0)


async def clear_user_preferences(db: AsyncSession, *, user_id: int) -> int:
    """清空用户全部偏好。"""

    validate_db_contract(
        "list_user_preferences",
        caller="api",
        operation="select",
        params={"user_id": user_id},
    )
    result = await db.execute(delete(UserPreference).where(UserPreference.user_id == user_id))
    return int(result.rowcount or 0)


def serialize_user_preference(item: UserPreference) -> dict[str, Any]:
    """统一输出结构。"""

    return {
        "key": item.key,
        "value": item.value,
        "category": item.category,
        "confidence": item.confidence,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
