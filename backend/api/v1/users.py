from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from api.v1.auth import get_current_user
from db.models import User

router = APIRouter()


class PreferencesUpdate(BaseModel):
    preferences: dict


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "is_guest": current_user.is_guest,
        "preferences": current_user.preferences,
    }


@router.patch("/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.preferences = {**current_user.preferences, **body.preferences}
    await db.commit()
    return {"preferences": current_user.preferences}
