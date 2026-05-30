from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
from core.session import create_guest_session, delete_session, get_session
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
    GUEST_FORBIDDEN = "GUEST_FORBIDDEN"
    GUEST_NOT_FOUND = "GUEST_NOT_FOUND"
    GUEST_ALREADY_REGISTERED = "GUEST_ALREADY_REGISTERED"


def _error(code: str, detail: str, http_status: int = 400) -> HTTPException:
    return HTTPException(status_code=http_status, detail={"code": code, "detail": detail})


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class GuestUpgradeRequest(BaseModel):
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

async def _make_token_response(user: User, redis: Redis) -> TokenResponse:
    user_id = str(user.id)
    access_token, jti, _ = make_access_token(user_id)
    refresh_token = make_refresh_token(user_id)
    await redis.setex(f"refresh_token:{user_id}", settings.JWT_EXPIRE_MINUTES * 60, refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id,
        is_guest=user.is_guest,
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
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> User:
    # 1. 优先 Bearer token (JWT)
    if token:
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

    # 2. 回退 Session cookie (游客)
    session_id = request.cookies.get("session_id")
    if session_id:
        session = await get_session(redis, session_id)
        if session:
            user = await db.get(User, uuid.UUID(session["user_id"]))
            if user:
                return user

    raise _error(ErrorCode.AUTH_NOT_AUTHENTICATED, "Not authenticated", 401)


async def require_member(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.is_guest:
        raise _error(ErrorCode.GUEST_FORBIDDEN, "Login required for this action", 403)
    return current_user


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/guest")
async def guest_login(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    user = User(fingerprint=None, is_guest=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    session_id = await create_guest_session(redis, str(user.id))
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/",
    )
    return {"user_id": str(user.id), "is_guest": True}


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
    return await _make_token_response(user, redis)


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

    return await _make_token_response(user, redis)


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
    return await _make_token_response(user, redis)


@router.post("/logout")
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    redis: Redis = Depends(get_redis),
):
    if token:
        await _blacklist_token(token, redis)
    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(redis, session_id)
    return {"message": "Logged out"}


@router.post("/upgrade", response_model=TokenResponse)
async def upgrade_guest(
    req: GuestUpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    if not current_user.is_guest:
        raise _error(ErrorCode.GUEST_ALREADY_REGISTERED, "Already a registered user")

    err = validate_password(req.password)
    if err:
        raise _error(ErrorCode.AUTH_WEAK_PASSWORD, err)

    # 检查邮箱是否被占用
    email_result = await db.execute(select(User).where(User.email == req.email))
    if email_result.scalar_one_or_none():
        raise _error(ErrorCode.AUTH_EMAIL_EXISTS, "Email already registered")

    # 升级游客为注册用户
    current_user.email = req.email
    current_user.hashed_password = pwd_ctx.hash(req.password)
    current_user.is_guest = False
    current_user.fingerprint = None
    await db.commit()
    await db.refresh(current_user)

    return await _make_token_response(current_user, redis)
