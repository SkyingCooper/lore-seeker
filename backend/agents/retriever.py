"""检索 Agent：向量检索 + 重排序 + 问答。"""
from core.llm_router import get_llm
from core.embedding_router import get_embeddings, rerank
from core.prompt_loader import get_prompt, render_prompt
from agents.guardrails import (
    AgentErrorContext,
    AgentOutputContext,
    AgentRunContext,
    ModelRequestContext,
    ToolCallContext,
    ToolResultContext,
    after_run,
    after_tool_call,
    before_model_request,
    before_run,
    before_tool_call,
    on_error,
    on_tool_error,
)
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def retrieve(query: str, db: AsyncSession, user_id: int, top_k: int = 20) -> list[dict]:
    """向量检索 + 重排序，返回最相关的 chunks。"""
    before_run(
        AgentRunContext(
            agent_name="retriever",
            responsibility="user_isolated_vector_retrieval",
            operation="retrieve_user_knowledge_chunks",
            user_id=user_id,
            state={"query": query, "user_id": user_id},
        )
    )
    before_tool_call(
        ToolCallContext(
            agent_name="retriever",
            tool_name="embedding",
            operation="embed_user_query",
            args={"query": query},
        )
    )
    try:
        query_vec = (await get_embeddings([query]))[0]
    except Exception as exc:
        on_tool_error(
            AgentErrorContext(
                agent_name="retriever",
                stage="on_tool_error",
                operation="embed_user_query",
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=True,
            )
        )
        raise
    after_tool_call(
        ToolResultContext(
            agent_name="retriever",
            tool_name="embedding",
            operation="embed_user_query",
            result={"vector_dim": len(query_vec)},
        )
    )

    # 通过 reports -> search_tasks 过滤 user_id，避免跨用户检索知识切片。
    before_tool_call(
        ToolCallContext(
            agent_name="retriever",
            tool_name="postgres",
            operation="retrieve_user_knowledge_chunks",
            args={"user_id": user_id, "top_k": top_k},
        )
    )
    stmt = text("""
        SELECT kc.id, kc.content, kc.report_id, kc.metadata,
               1 - (kc.embedding <=> :vec::vector) AS score
        FROM knowledge_chunks kc
        JOIN reports r ON r.id = kc.report_id
        JOIN search_tasks st ON st.id = r.task_id
        WHERE st.user_id = :user_id
          AND st.deleted_at IS NULL
        ORDER BY kc.embedding <=> :vec::vector
        LIMIT :top_k
    """)
    try:
        rows = (await db.execute(stmt, {"vec": str(query_vec), "user_id": user_id, "top_k": top_k})).fetchall()
    except Exception as exc:
        on_tool_error(
            AgentErrorContext(
                agent_name="retriever",
                stage="on_tool_error",
                operation="retrieve_user_knowledge_chunks",
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=True,
            )
        )
        raise
    after_tool_call(
        ToolResultContext(
            agent_name="retriever",
            tool_name="postgres",
            operation="retrieve_user_knowledge_chunks",
            result={"row_count": len(rows)},
        )
    )

    if not rows:
        return []

    docs = [{"id": str(r.id), "content": r.content, "report_id": str(r.report_id), "score": r.score} for r in rows]

    # 重排序
    before_tool_call(
        ToolCallContext(
            agent_name="retriever",
            tool_name="reranker",
            operation="rerank_retrieved_chunks",
            args={"query": query, "chunk_count": len(docs)},
        )
    )
    try:
        reranked = await rerank(query, [d["content"] for d in docs])
    except Exception as exc:
        on_tool_error(
            AgentErrorContext(
                agent_name="retriever",
                stage="on_tool_error",
                operation="rerank_retrieved_chunks",
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=True,
            )
        )
        raise
    after_tool_call(
        ToolResultContext(
            agent_name="retriever",
            tool_name="reranker",
            operation="rerank_retrieved_chunks",
            result={"reranked_count": len(reranked)},
        )
    )
    result = []
    for r in reranked[:5]:
        d = docs[r["index"]]
        d["rerank_score"] = r["score"]
        result.append(d)
    after_run(
        AgentOutputContext(
            agent_name="retriever",
            operation="return_sources",
            result={"sources": result},
        )
    )
    return result


async def answer(query: str, chunks: list[dict]) -> str:
    """基于检索结果生成回答。"""
    operation = "generate_context_grounded_answer"
    before_run(
        AgentRunContext(
            agent_name="retriever",
            responsibility="context_grounded_answer",
            operation=operation,
            state={"query": query, "retrieved_chunks": chunks},
        )
    )
    context = "\n\n".join(f"[{i+1}] {c['content']}" for i, c in enumerate(chunks))
    system_prompt = get_prompt("retriever.answer.system")
    user_prompt = render_prompt("retriever.answer.user", query=query, context=context)
    try:
        llm = get_llm(temperature=0.3)
        before_model_request(
            ModelRequestContext(
                agent_name="retriever",
                operation=operation,
                temperature=0.3,
                prompt_chars=len(system_prompt) + len(user_prompt),
            )
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        resp = await llm.ainvoke(messages)
        after_run(
            AgentOutputContext(
                agent_name="retriever",
                operation=operation,
                result={"answer": resp.content},
            )
        )
        return resp.content
    except Exception as exc:
        on_error(
            AgentErrorContext(
                agent_name="retriever",
                stage="on_error",
                operation=operation,
                error_type=type(exc).__name__,
                message=str(exc),
                retryable=True,
            )
        )
        raise
