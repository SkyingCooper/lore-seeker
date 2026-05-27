from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import uuid

from core.config import settings
from core.database import get_db
from db.models import User

router = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class GuestRequest(BaseModel):
    fingerprint: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    is_guest: bool


def _make_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/guest", response_model=TokenResponse)
async def guest_login(req: GuestRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.fingerprint == req.fingerprint))
    user = result.scalar_one_or_none()
    if not user:
        user = User(fingerprint=req.fingerprint, is_guest=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return TokenResponse(access_token=_make_token(str(user.id)), user_id=str(user.id), is_guest=True)


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=req.email, hashed_password=pwd_ctx.hash(req.password), is_guest=False)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return TokenResponse(access_token=_make_token(str(user.id)), user_id=str(user.id), is_guest=False)


@router.post("/login", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not user.hashed_password or not pwd_ctx.verify(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    return TokenResponse(access_token=_make_token(str(user.id)), user_id=str(user.id), is_guest=False)
