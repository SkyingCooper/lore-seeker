from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import TokenConsumptionLog, User, UserTokenBalance
from services.user_preference_service import (
    clear_user_preferences,
    delete_user_preference,
    list_user_preferences,
    load_preferences_dict,
    serialize_user_preference,
    upsert_user_preference,
)

router = APIRouter()


class PreferencesUpdate(BaseModel):
    preferences: dict[str, object]


class PreferenceItemUpdate(BaseModel):
    value: object


class PreferenceItemResponse(BaseModel):
    key: str
    value: object | None
    category: str
    confidence: float | None = None
    updated_at: str | None = None
    created_at: str | None = None


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await load_preferences_dict(db, user_id=current_user.id)
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
        await upsert_user_preference(db, user_id=current_user.id, key=str(key), value=value)
    await db.commit()
    return {"preferences": await load_preferences_dict(db, user_id=current_user.id)}

@router.get("/me/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await list_user_preferences(db, user_id=current_user.id)
    return {"items": [serialize_user_preference(item) for item in rows]}


@router.put("/me/preferences/{key}", response_model=PreferenceItemResponse)
async def put_preference(
    key: str,
    body: PreferenceItemUpdate,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    item = await upsert_user_preference(
        db,
        user_id=current_user.id,
        key=key,
        value=body.value,
        category="explicit",
        confidence=None,
    )
    await db.commit()
    await db.refresh(item)
    return serialize_user_preference(item)


@router.delete("/me/preferences/{key}")
async def revoke_preference(
    key: str,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_user_preference(db, user_id=current_user.id, key=key)
    await db.commit()
    if not deleted:
        raise HTTPException(404, detail={"code": "PREFERENCE_NOT_FOUND", "detail": "Preference not found"})
    return {"key": key, "deleted": True}


@router.delete("/me/preferences")
async def clear_preferences(
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    deleted = await clear_user_preferences(db, user_id=current_user.id)
    await db.commit()
    return {"deleted_count": deleted}


@router.get("/me/token-balance")
async def get_token_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    balance = await db.get(UserTokenBalance, str(current_user.id))
    if not balance:
        return {
            "user_id": str(current_user.id),
            "balance": 0,
            "total_consumed": 0,
            "last_reset_at": None,
            "updated_at": None,
        }
    return {
        "user_id": balance.user_id,
        "balance": balance.balance,
        "total_consumed": balance.total_consumed,
        "last_reset_at": balance.last_reset_at.isoformat() if balance.last_reset_at else None,
        "updated_at": balance.updated_at.isoformat() if balance.updated_at else None,
    }


@router.get("/me/token-consumption")
async def list_token_consumption(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    safe_limit = min(max(limit, 1), 100)
    rows = await db.execute(
        select(TokenConsumptionLog)
        .where(TokenConsumptionLog.user_id == str(current_user.id))
        .order_by(TokenConsumptionLog.created_at.desc())
        .limit(safe_limit)
    )
    return {
        "items": [
            {
                "id": item.id,
                "user_id": item.user_id,
                "task_id": item.task_id,
                "stage": item.stage,
                "provider": item.provider,
                "model": item.model,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "estimated_before": item.estimated_before,
                "actual_consumed": item.actual_consumed,
                "balance_after": item.balance_after,
                "metadata": item.metadata_,
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in rows.scalars()
        ]
    }
