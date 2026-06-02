import uuid

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from core.config import settings
from core.redis_client import get_redis

router = APIRouter()


@router.post("/captcha/challenge")
async def get_challenge(redis: Redis = Depends(get_redis)):
    token = uuid.uuid4().hex
    await redis.setex(f"captcha:{token}", settings.CAPTCHA_TTL_SECONDS, "1")
    return {"slider_token": token}


async def verify_captcha(redis: Redis, slider_token: str, slider_x: int) -> None:
    stored = await redis.get(f"captcha:{slider_token}")
    if stored is None:
        raise HTTPException(400, detail={"code": "CAPTCHA_FAILED", "detail": "Captcha expired, please retry"})
    # 验证滑动距离合理（非脚本直接提交）
    if slider_x < 30:
        raise HTTPException(400, detail={"code": "CAPTCHA_FAILED", "detail": "Verification failed, please retry"})
    await redis.delete(f"captcha:{slider_token}")
