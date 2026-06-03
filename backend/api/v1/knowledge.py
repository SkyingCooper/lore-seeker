from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from core.redis_client import get_redis
from api.v1.auth import get_current_user, require_member
from db.models import User
from agents.retriever import run_retriever_agent
from redis.asyncio import Redis
from services.retriever_memory import preload_retriever_context, record_retriever_turn

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    session_id: str = "default"


@router.post("/query")
async def query_knowledge(
    body: QueryRequest,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    memory_context = await preload_retriever_context(db, redis, user_id=current_user.id, session_id=body.session_id)
    result = await run_retriever_agent(
        body.query,
        db,
        user_id=current_user.id,
        top_k=body.top_k,
        memory_context=memory_context,
    )
    chunks = result["chunks"]
    response = result["answer"]
    await record_retriever_turn(
        db,
        redis,
        user_id=current_user.id,
        session_id=body.session_id,
        user_message=body.query,
        assistant_message=response,
    )
    await db.commit()
    return {
        "answer": response,
        "sources": [{"content": c["content"][:200], "report_id": c["report_id"], "score": c.get("rerank_score")} for c in chunks],
    }
