"""检索 Agent：关键词检索 + 向量检索 + RRF 融合 + 重排序 + 问答。"""
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
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
    build_guarded_pydantic_agent,
    on_error,
    on_tool_error,
)
from agents.pydantic_runtime import build_agent_model, usage_from_pydantic_result
from agents.token_usage import merge_stage_usage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from constraint.validation.validator import validate_db_contract
from services.context_manager import ContextItem, build_context

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "retriever.yaml"


class RetrieverAnswerOutput(BaseModel):
    answer: str = ""
    sources_used: list[int] = Field(default_factory=list)


RETRIEVER_ANSWER_AGENT = build_guarded_pydantic_agent(
    "retriever",
    instructions="Answer only from user-isolated retrieved context and cite source indexes.",
)


async def retrieve(query: str, db: AsyncSession, user_id: int, top_k: int = 20) -> list[dict]:
    """双路检索 + RRF + 重排序，返回最相关的 chunks。"""
    cfg = _retriever_config()
    keyword_top_k = int(cfg["keyword_retrieval"].get("top_k", 20))
    vector_top_k = int(cfg["vector_retrieval"].get("top_k", 20))
    candidate_top_k = int(cfg["fusion"].get("candidate_top_k", 30))
    rrf_k = int(cfg["fusion"].get("rrf_k", 60))
    rerank_top_k = min(top_k, int(cfg["rerank"].get("top_k", 5)))
    rerank_min_score = float(cfg["rerank"].get("min_score", 0.5))

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
            args={"user_id": user_id, "keyword_top_k": keyword_top_k, "vector_top_k": vector_top_k},
        )
    )
    validate_db_contract(
        "retrieve_knowledge",
        caller="retriever",
        operation="select",
        params={"user_id": user_id, "query_embedding": query_vec, "query": query},
    )
    vector_stmt = text("""
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
    keyword_stmt = text("""
        SELECT kc.id, kc.content, kc.report_id, kc.metadata,
               ts_rank_cd(kc.search_vector, plainto_tsquery('simple', :query)) AS score
        FROM knowledge_chunks kc
        JOIN reports r ON r.id = kc.report_id
        JOIN search_tasks st ON st.id = r.task_id
        WHERE st.user_id = :user_id
          AND st.deleted_at IS NULL
          AND kc.search_vector @@ plainto_tsquery('simple', :query)
        ORDER BY score DESC
        LIMIT :top_k
    """)
    try:
        vector_rows = (await db.execute(vector_stmt, {"vec": str(query_vec), "user_id": user_id, "top_k": vector_top_k})).fetchall()
        keyword_rows = (await db.execute(keyword_stmt, {"query": query, "user_id": user_id, "top_k": keyword_top_k})).fetchall()
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
            result={"vector_count": len(vector_rows), "keyword_count": len(keyword_rows)},
        )
    )

    if not vector_rows and not keyword_rows:
        return []

    docs = _rrf_fuse(keyword_rows, vector_rows, rrf_k=rrf_k, limit=candidate_top_k)

    # 重排序
    before_tool_call(
        ToolCallContext(
            agent_name="retriever",
            tool_name="reranker",
            operation="rerank_retrieved_chunks",
            args={"query": query, "chunk_count": len(docs), "min_score": rerank_min_score},
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
    for r in reranked[:rerank_top_k]:
        if float(r["score"]) < rerank_min_score:
            continue
        d = docs[r["index"]]
        d["rerank_score"] = r["score"]
        result.append(d)
    if not result:
        result = docs[:rerank_top_k]
    after_run(
        AgentOutputContext(
            agent_name="retriever",
            operation="return_sources",
            result={"sources": result},
        )
    )
    return result


async def answer(query: str, chunks: list[dict], *, memory_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """基于检索结果生成回答。"""
    if not chunks:
        return "没有在当前用户知识库中检索到足够相关的内容。请补充问题细节，或先创建相关主题任务生成报告。"

    operation = "generate_context_grounded_answer"
    before_run(
        AgentRunContext(
            agent_name="retriever",
            responsibility="context_grounded_answer",
            operation=operation,
            state={"query": query, "retrieved_chunks": chunks},
        )
    )
    context_items = [
            ContextItem(
                priority="P2",
                name=f"source_{i + 1}",
                content=f"[{i + 1}] report_id={c['report_id']} score={c.get('rerank_score', c.get('score'))}\n{c['content']}",
            )
            for i, c in enumerate(chunks)
        ]
    if memory_context:
        context_items.append(
            ContextItem(
                priority="P3",
                name="user_memory",
                content=_memory_context_text(memory_context),
            )
        )
    context_pack = build_context(
        context_items,
        scenario="agent_communication",
    )
    context = context_pack["context"]
    system_prompt = get_prompt("retriever.answer.system")
    user_prompt = render_prompt("retriever.answer.user", query=query, context=context)
    model = build_agent_model("retriever")
    try:
        before_model_request(
            ModelRequestContext(
                agent_name="retriever",
                operation=operation,
                temperature=0.3,
                prompt_chars=len(system_prompt) + len(user_prompt),
            )
        )
        resp = await RETRIEVER_ANSWER_AGENT.run(
            user_prompt,
            output_type=RetrieverAnswerOutput,
            model=model,
            instructions=system_prompt,
            metadata={"agent": "retriever", "operation": operation},
        )
        token_usage = merge_stage_usage(
            None,
            stage="retrieve",
            usage=usage_from_pydantic_result(resp),
            model=model.model_name if hasattr(model, "model_name") else None,
        )
        after_run(
            AgentOutputContext(
                agent_name="retriever",
                operation=operation,
                result={
                    "answer": resp.output.answer,
                    "sources_used": resp.output.sources_used,
                    "token_usage": token_usage,
                    "context_token_estimate": context_pack["token_estimate"],
                },
            )
        )
        return {
            "answer": resp.output.answer,
            "sources_used": resp.output.sources_used,
            "token_usage": token_usage,
            "context_token_estimate": context_pack["token_estimate"],
        }
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


async def run_retriever_agent(
    query: str,
    db: AsyncSession,
    user_id: int,
    *,
    top_k: int = 5,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """原生可测试的 Retriever 入口：检索 + 回答。"""
    intent = _classify_intent(query)
    if intent["confidence"] < 0.6:
        return {
            "answer": "我还不能确定你的问题具体指向哪一部分。请补充主题、上下文或你想对比的对象。",
            "chunks": [],
            "token_usage": merge_stage_usage(
                None,
                stage="retrieve",
                usage={"input_tokens": 0, "output_tokens": 0, "total": 0},
                model=None,
            ),
            "intent": intent,
        }

    effective_query = _rewrite_query_for_retry(query, memory_context)
    chunks = await retrieve(effective_query, db, user_id=user_id, top_k=top_k * 4)
    if not chunks:
        fallback = _build_no_hit_message(query, memory_context)
        return {
            "answer": fallback,
            "chunks": [],
            "token_usage": merge_stage_usage(
                None,
                stage="retrieve",
                usage={"input_tokens": 0, "output_tokens": 0, "total": 0},
                model=None,
            ),
            "intent": intent,
        }
    answer_result = await answer(effective_query, chunks, memory_context=memory_context)
    token_usage = merge_stage_usage(
        answer_result.get("token_usage"),
        stage="context_manager",
        usage={"input_tokens": int(answer_result.get("context_token_estimate") or 0), "output_tokens": 0, "total": int(answer_result.get("context_token_estimate") or 0)},
        model="rule_based_context",
    )
    return {"answer": answer_result["answer"], "chunks": chunks, "token_usage": token_usage, "intent": intent}


def _retriever_config() -> dict[str, Any]:
    default = {
        "keyword_retrieval": {"top_k": 20},
        "vector_retrieval": {"top_k": 20},
        "fusion": {"rrf_k": 60, "candidate_top_k": 30},
        "rerank": {"top_k": 5, "min_score": 0.5},
    }
    if not CONFIG_PATH.exists():
        return default
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        data = (yaml.safe_load(f) or {}).get("retriever", {})
    return {**default, **data}


def _classify_intent(query: str) -> dict[str, Any]:
    text = query.strip()
    if len(text) < 4:
        return {"intent": "unknown", "confidence": 0.3}
    if any(keyword in text.lower() for keyword in ("怎么", "如何", "why", "how", "什么", "which")):
        return {"intent": "knowledge_query", "confidence": 0.85}
    return {"intent": "knowledge_query", "confidence": 0.65}


def _rewrite_query_for_retry(query: str, memory_context: dict[str, Any] | None) -> str:
    if not any(term in query for term in ("不对", "不是这个", "重新回答", "重答")):
        return query
    episodic = (memory_context or {}).get("episodic") or []
    for item in reversed(episodic):
        user_message = item.get("user_message") or item.get("content")
        if user_message and user_message != query:
            return f"{user_message}\n补充要求：用户对上一轮回答不满意，请重新回答并更严格依据知识库证据。"
    return query


def _build_no_hit_message(query: str, memory_context: dict[str, Any] | None) -> str:
    semantic = (memory_context or {}).get("semantic") or []
    if semantic:
        top_titles = "、".join(item.get("title", "") for item in semantic[:3] if item.get("title"))
        if top_titles:
            return f"当前知识库里没有检索到足够直接的证据。你可以换一种问法，或围绕这些已知主题继续提问：{top_titles}。"
    return f"当前知识库里没有检索到与“{query}”足够相关的内容。请缩小范围、补充限定条件，或先创建相关主题任务。"


def _row_to_doc(row, *, channel: str, rank: int) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "content": row.content,
        "report_id": str(row.report_id),
        "score": float(row.score or 0),
        "channels": [channel],
        "ranks": {channel: rank},
    }


def _rrf_fuse(keyword_rows, vector_rows, *, rrf_k: int, limit: int) -> list[dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}

    for channel, rows in (("keyword", keyword_rows), ("vector", vector_rows)):
        for rank, row in enumerate(rows, start=1):
            key = str(row.id)
            if key not in docs:
                docs[key] = _row_to_doc(row, channel=channel, rank=rank)
                docs[key]["rrf_score"] = 0.0
            else:
                docs[key]["channels"].append(channel)
                docs[key]["ranks"][channel] = rank
            docs[key]["rrf_score"] += 1.0 / (rrf_k + rank)

    return sorted(docs.values(), key=lambda item: item["rrf_score"], reverse=True)[:limit]


def _memory_context_text(memory_context: dict[str, Any]) -> str:
    episodic = memory_context.get("episodic") or []
    semantic = memory_context.get("semantic") or []
    parts: list[str] = []
    if semantic:
        parts.append("长期语义记忆：")
        parts.extend(f"- {item.get('title')}: {item.get('summary')}" for item in semantic[:8])
    if episodic:
        parts.append("近期情景记忆：")
        parts.extend(f"- {item.get('content')}" for item in episodic[:5])
    return "\n".join(parts)
