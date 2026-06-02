from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import User
from agents.retriever import retrieve, answer

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/query")
async def query_knowledge(
    body: QueryRequest,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    chunks = await retrieve(body.query, db, user_id=current_user.id, top_k=body.top_k * 4)
    response = await answer(body.query, chunks)
    return {
        "answer": response,
        "sources": [{"content": c["content"][:200], "report_id": c["report_id"], "score": c.get("rerank_score")} for c in chunks],
    }
