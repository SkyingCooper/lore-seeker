"""Retriever integration tests for deterministic recall quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents import retriever


@dataclass
class _Row:
    id: int
    content: str
    report_id: int
    metadata: dict[str, Any]
    score: float


class _Result:
    def __init__(self, rows: list[_Row]):
        self._rows = rows

    def fetchall(self) -> list[_Row]:
        return self._rows


class _FakeAsyncSession:
    def __init__(self, query_rows: dict[str, dict[str, list[_Row]]]):
        self.query_rows = query_rows
        self.current_query: str | None = None

    async def execute(self, stmt, params):
        query = params.get("query") or self.current_query
        sql = str(stmt)
        if "ts_rank_cd" in sql:
            rows = self.query_rows[query]["keyword"]
        else:
            rows = self.query_rows[query]["vector"]
        return _Result(rows)


@pytest.mark.asyncio
async def test_retriever_hit_rate_contains_expected_golden_answers() -> None:
    cases = {
        "asyncio 事件循环是什么": {
            "expected": "事件循环",
            "keyword": [
                _Row(1, "asyncio 的事件循环负责调度协程、回调和 IO 事件。", 101, {}, 0.95),
                _Row(2, "无关内容", 102, {}, 0.2),
            ],
            "vector": [
                _Row(3, "事件循环是 asyncio 的核心调度机制。", 103, {}, 0.91),
            ],
        },
        "pgvector HNSW 索引有什么作用": {
            "expected": "近似最近邻",
            "keyword": [
                _Row(4, "HNSW 索引用于向量检索中的近似最近邻搜索。", 201, {}, 0.97),
            ],
            "vector": [
                _Row(5, "pgvector 通过 HNSW 提升 ANN 查询性能。", 202, {}, 0.93),
            ],
        },
    }
    db = _FakeAsyncSession(cases)
    hit_count = 0

    async def fake_embeddings(_texts: list[str]):
        return [[0.1, 0.2, 0.3]], {"input_tokens": 3, "output_tokens": 0, "total": 3}

    async def fake_rerank(query: str, docs: list[str]):
        return (
            [{"index": idx, "score": 0.9 if cases[query]["expected"] in doc else 0.2} for idx, doc in enumerate(docs)],
            {"input_tokens": 5, "output_tokens": 1, "total": 6},
        )

    with patch.object(retriever, "get_embeddings_with_usage", new=AsyncMock(side_effect=fake_embeddings)), \
         patch.object(retriever, "rerank_with_usage", new=AsyncMock(side_effect=fake_rerank)):
        for query, case in cases.items():
            db.current_query = query
            docs = await retriever.retrieve(query, db, user_id=1, top_k=5)
            if any(case["expected"] in item["content"] for item in docs):
                hit_count += 1

    hit_rate = hit_count / len(cases)
    assert hit_rate == 1.0
    assert hit_rate >= 0.8
