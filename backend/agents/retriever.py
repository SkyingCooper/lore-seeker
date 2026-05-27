"""检索 Agent：向量检索 + 重排序 + 问答。"""
from core.llm_router import get_llm
from core.embedding_router import get_embeddings, rerank
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from db.models import KnowledgeChunk, Report


async def retrieve(query: str, db: AsyncSession, top_k: int = 20) -> list[dict]:
    """向量检索 + 重排序，返回最相关的 chunks。"""
    query_vec = (await get_embeddings([query]))[0]

    # pgvector 余弦相似度检索
    stmt = text("""
        SELECT kc.id, kc.content, kc.report_id, kc.metadata,
               1 - (kc.embedding <=> :vec::vector) AS score
        FROM knowledge_chunks kc
        ORDER BY kc.embedding <=> :vec::vector
        LIMIT :top_k
    """)
    rows = (await db.execute(stmt, {"vec": str(query_vec), "top_k": top_k})).fetchall()

    if not rows:
        return []

    docs = [{"id": str(r.id), "content": r.content, "report_id": str(r.report_id), "score": r.score} for r in rows]

    # 重排序
    reranked = await rerank(query, [d["content"] for d in docs])
    result = []
    for r in reranked[:5]:
        d = docs[r["index"]]
        d["rerank_score"] = r["score"]
        result.append(d)
    return result


async def answer(query: str, chunks: list[dict]) -> str:
    """基于检索结果生成回答。"""
    context = "\n\n".join(f"[{i+1}] {c['content']}" for i, c in enumerate(chunks))
    llm = get_llm(temperature=0.3)
    messages = [
        SystemMessage(content="你是一个知识库助手，根据提供的上下文回答用户问题。如果上下文不足，请说明。"),
        HumanMessage(content=f"问题：{query}\n\n上下文：\n{context}"),
    ]
    resp = await llm.ainvoke(messages)
    return resp.content
