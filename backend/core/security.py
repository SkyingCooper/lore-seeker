from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from jose import jwt

from core.config import settings


def validate_password(password: str) -> str | None:
    """校验密码强度，返回 None 表示通过，否则返回错误消息。"""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter"
    if not re.search(r"\d", password):
        return "Password must contain at least one digit"
    return None


def make_access_token(user_id: str) -> tuple[str, str, datetime]:
    """创建 access token，返回 (token, jti, expires_at)。"""
    jti = uuid.uuid4().hex
    expire = datetime.utcnow() + timedelta(minutes=30)
    payload = {"sub": user_id, "jti": jti, "exp": expire, "type": "access"}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire


def make_refresh_token(user_id: str) -> str:
    """创建 refresh token（每次生成唯一 jti，存储在 Redis 中）。"""
    jti = uuid.uuid4().hex
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "jti": jti, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码 JWT，不验证过期（过期检查由 jose 自动完成）。"""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
