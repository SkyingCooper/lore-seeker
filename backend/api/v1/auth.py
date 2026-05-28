from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from jose import JWTError
from redis.asyncio import Redis

from core.config import settings
from core.database import get_db
from core.redis_client import get_redis
from core.security import decode_token, make_access_token, make_refresh_token, validate_password
from db.models import User

router = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ─── Error codes ──────────────────────────────────────────────────────────────

class ErrorCode:
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_EMAIL_EXISTS = "AUTH_EMAIL_EXISTS"
    AUTH_WEAK_PASSWORD = "AUTH_WEAK_PASSWORD"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_BLACKLISTED = "AUTH_TOKEN_BLACKLISTED"
    AUTH_REFRESH_INVALID = "AUTH_REFRESH_INVALID"
    AUTH_NOT_AUTHENTICATED = "AUTH_NOT_AUTHENTICATED"
    GUEST_NOT_FOUND = "GUEST_NOT_FOUND"
    GUEST_ALREADY_REGISTERED = "GUEST_ALREADY_REGISTERED"


def _error(code: str, detail: str, http_status: int = 400) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "detail": detail})


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class GuestRequest(BaseModel):
    fingerprint: str


class GuestUpgradeRequest(BaseModel):
    fingerprint: str
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    is_guest: bool


# ─── Token helpers ────────────────────────────────────────────────────────────

async def _make_token(user_id: str, redis: Redis) -> TokenResponse:
    access_token, jti, _ = make_access_token(user_id)
    refresh_token = make_refresh_token(user_id)
    # 存储 refresh token 到 Redis
    await redis.setex(f"refresh_token:{user_id}", settings.JWT_EXPIRE_MINUTES * 60, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        is_guest=False,
    )


async def _make_guest_token(user_id: str, redis: Redis) -> TokenResponse:
    access_token, jti, _ = make_access_token(user_id)
    refresh_token = make_refresh_token(user_id)
    await redis.setex(f"refresh_token:{user_id}", settings.JWT_EXPIRE_MINUTES * 60, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        is_guest=True,
    )


async def _blacklist_token(token: str, redis: Redis) -> None:
    """将 access token 加入黑名单，TTL 为其剩余有效期。"""
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = datetime.utcfromtimestamp(payload["exp"])
        ttl = max(0, int((exp - datetime.utcnow()).total_seconds()))
        if jti and ttl > 0:
            await redis.setex(f"bl_access:{jti}", ttl, "1")
    except JWTError:
        pass  # token 已过期则无需加入黑名单


async def _is_blacklisted(token: str, redis: Redis) -> bool:
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            return await redis.exists(f"bl_access:{jti}") > 0
    except JWTError:
        return False
    return False


# ─── Auth dependency ──────────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    if not token:
        raise _error(ErrorCode.AUTH_NOT_AUTHENTICATED, "Not authenticated", 401)
    try:
        payload = decode_token(token)
    except JWTError:
        raise _error(ErrorCode.AUTH_TOKEN_EXPIRED, "Token expired or invalid", 401)

    if payload.get("type") != "access":
        raise _error(ErrorCode.AUTH_TOKEN_EXPIRED, "Invalid token type", 401)

    if await _is_blacklisted(token, redis):
        raise _error(ErrorCode.AUTH_TOKEN_BLACKLISTED, "Token has been revoked", 401)

    user = await db.get(User, uuid.UUID(payload["sub"]))
    if not user:
        raise _error(ErrorCode.AUTH_NOT_AUTHENTICATED, "User not found", 401)
    return user


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/guest", response_model=TokenResponse)
async def guest_login(req: GuestRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    result = await db.execute(select(User).where(User.fingerprint == req.fingerprint))
    user = result.scalar_one_or_none()
    if not user:
        user = User(fingerprint=req.fingerprint, is_guest=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return await _make_guest_token(str(user.id), redis)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    err = validate_password(req.password)
    if err:
        raise _error(ErrorCode.AUTH_WEAK_PASSWORD, err)

    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise _error(ErrorCode.AUTH_EMAIL_EXISTS, "Email already registered")

    user = User(email=req.email, hashed_password=pwd_ctx.hash(req.password), is_guest=False)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _make_token(str(user.id), redis)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not pwd_ctx.verify(form.password, user.hashed_password):
        raise _error(ErrorCode.AUTH_INVALID_CREDENTIALS, "Incorrect email or password")

    return await _make_token(str(user.id), redis)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    try:
        payload = decode_token(req.refresh_token)
    except JWTError:
        raise _error(ErrorCode.AUTH_REFRESH_INVALID, "Invalid or expired refresh token", 401)

    if payload.get("type") != "refresh":
        raise _error(ErrorCode.AUTH_REFRESH_INVALID, "Invalid token type", 401)

    user_id = payload["sub"]

    # 验证 refresh token 是否与 Redis 中存储的一致
    stored = await redis.get(f"refresh_token:{user_id}")
    if not stored or stored != req.refresh_token:
        raise _error(ErrorCode.AUTH_REFRESH_INVALID, "Refresh token has been revoked", 401)

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise _error(ErrorCode.AUTH_NOT_AUTHENTICATED, "User not found", 401)

    # 轮换 refresh token
    return await (_make_guest_token(user_id, redis) if user.is_guest else _make_token(user_id, redis))


@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    redis: Redis = Depends(get_redis),
):
    if not token:
        return {"message": "Logged out"}
    await _blacklist_token(token, redis)
    return {"message": "Logged out"}


@router.post("/upgrade", response_model=TokenResponse)
async def upgrade_guest(
    req: GuestUpgradeRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    err = validate_password(req.password)
    if err:
        raise _error(ErrorCode.AUTH_WEAK_PASSWORD, err)

    # 查找游客
    result = await db.execute(select(User).where(User.fingerprint == req.fingerprint))
    guest = result.scalar_one_or_none()
    if not guest:
        raise _error(ErrorCode.GUEST_NOT_FOUND, "Guest not found with this fingerprint", 404)
    if not guest.is_guest:
        raise _error(ErrorCode.GUEST_ALREADY_REGISTERED, "This fingerprint is already linked to a registered account")

    # 检查邮箱是否被占用
    email_result = await db.execute(select(User).where(User.email == req.email))
    if email_result.scalar_one_or_none():
        raise _error(ErrorCode.AUTH_EMAIL_EXISTS, "Email already registered")

    # 升级游客为注册用户
    guest.email = req.email
    guest.hashed_password = pwd_ctx.hash(req.password)
    guest.is_guest = False
    await db.commit()
    await db.refresh(guest)

    return await _make_token(str(guest.id), redis)
