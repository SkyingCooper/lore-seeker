from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import User, UserPreference

router = APIRouter()


class PreferencesUpdate(BaseModel):
    preferences: dict


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await _load_preferences_dict(db, current_user.id)
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "avatar_url": current_user.avatar_url,
        "is_guest": current_user.is_guest,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "preferences": prefs,
    }


@router.patch("/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    for key, value in body.preferences.items():
        await _upsert_preference(db, current_user.id, str(key), value)
    await db.commit()
    return {"preferences": await _load_preferences_dict(db, current_user.id)}


async def _load_preferences_dict(db: AsyncSession, user_id: int) -> dict[str, Any]:
    rows = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id).order_by(UserPreference.updated_at.desc())
    )
    return {row.key: row.value for row in rows.scalars()}


async def _upsert_preference(db: AsyncSession, user_id: int, key: str, value: Any) -> UserPreference:
    existing = await db.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.key == key,
        )
    )
    if existing:
        existing.value = value
        existing.category = "explicit"
        existing.confidence = None
        existing.updated_at = datetime.utcnow()
        return existing

    preference = UserPreference(
        user_id=user_id,
        key=key,
        value=value,
        category="explicit",
        confidence=None,
    )
    db.add(preference)
    return preference
