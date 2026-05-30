from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import User

router = APIRouter()


class PreferencesUpdate(BaseModel):
    preferences: dict


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    prefs = await current_user.awaitable_attrs.preferences
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
    current_user.preferences = {**current_user.preferences, **body.preferences}
    await db.commit()
    return {"preferences": current_user.preferences}
