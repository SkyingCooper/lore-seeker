from core.config import settings
from typing import List


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """统一 embedding 入口，根据配置路由到不同厂商。"""
    p = settings.EMBEDDING_PROVIDER

    if p == "dashscope":
        return await _dashscope_embed(texts)
    if p == "openai":
        return await _openai_embed(texts)
    if p == "jina":
        return await _jina_embed(texts)
    raise ValueError(f"Unknown embedding provider: {p}")


async def rerank(query: str, documents: List[str]) -> List[dict]:
    """统一重排序入口。返回 [{index, score, text}]。"""
    p = settings.RERANKER_PROVIDER

    if p == "dashscope":
        return await _dashscope_rerank(query, documents)
    if p == "jina":
        return await _jina_rerank(query, documents)
    raise ValueError(f"Unknown reranker provider: {p}")


async def _dashscope_embed(texts: List[str]) -> List[List[float]]:
    import httpx

    url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.DASHSCOPE_EMBEDDING_MODEL,
        "input": {"texts": texts},
        "parameters": {"text_type": "document"},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return [item["embedding"] for item in data["output"]["embeddings"]]


async def _dashscope_rerank(query: str, documents: List[str]) -> List[dict]:
    import httpx

    url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    headers = {
        "Authorization": f"Bearer {settings.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.DASHSCOPE_RERANKER_MODEL,
        "input": {"query": query, "documents": documents},
        "parameters": {"return_documents": True, "top_n": len(documents)},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return [
        {"index": r["index"], "score": r["relevance_score"], "text": r["document"]["text"]}
        for r in data["output"]["results"]
    ]


async def _openai_embed(texts: List[str]) -> List[List[float]]:
    import httpx

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"model": "text-embedding-3-small", "input": texts}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.OPENAI_BASE_URL}/embeddings", json=payload, headers=headers
        )
        resp.raise_for_status()
        data = resp.json()
    return [item["embedding"] for item in data["data"]]


async def _jina_embed(texts: List[str]) -> List[List[float]]:
    import httpx

    headers = {
        "Authorization": f"Bearer {settings.JINA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.JINA_EMBEDDING_MODEL,
        "input": texts,
        "task": "retrieval.passage",
        "dimensions": 1024,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.JINA_EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    return [item["embedding"] for item in data["data"]]


async def _jina_rerank(query: str, documents: List[str]) -> List[dict]:
    import httpx

    headers = {
        "Authorization": f"Bearer {settings.JINA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.JINA_RERANKER_MODEL,
        "query": query,
        "documents": documents,
        "top_n": len(documents),
        "return_documents": True,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.JINA_RERANKER_BASE_URL.rstrip('/')}/rerank",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "index": item["index"],
            "score": item["relevance_score"],
            "text": item.get("document", {}).get("text", documents[item["index"]]),
        }
        for item in data["results"]
    ]
