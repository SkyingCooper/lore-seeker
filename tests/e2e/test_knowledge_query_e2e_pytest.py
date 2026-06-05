"""FastAPI E2E tests for the current dialogue-style knowledge query API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.v1.auth import require_member
from core.database import get_db
from core.redis_client import get_redis
from db.models import User
from main import app


@dataclass
class _FakeDB:
    commits: int = 0
    turns: list[dict[str, Any]] = field(default_factory=list)

    async def commit(self) -> None:
        self.commits += 1


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, _ttl: int, value: str):
        self.store[key] = value


@pytest.mark.asyncio
async def test_knowledge_query_e2e_records_multi_turn_history_and_returns_answer() -> None:
    fake_db = _FakeDB()
    fake_redis = _FakeRedis()
    current_user = User(id=7, username="tester", is_guest=False)

    async def override_member():
        return current_user

    async def override_db():
        yield fake_db

    async def override_redis():
        yield fake_redis

    async def fake_preload(_db, redis, *, user_id: int, session_id: str):
        return {
            "episodic": fake_redis.store.get(f"turns:{user_id}:{session_id}", []),
            "semantic": [],
            "preferences": [],
        }

    async def fake_record_turn(_db, redis, *, user_id: int, session_id: str, user_message: str, assistant_message: str):
        key = f"turns:{user_id}:{session_id}"
        turns = list(fake_redis.store.get(key, []))
        turns.append({"user_message": user_message, "assistant_message": assistant_message})
        fake_redis.store[key] = turns
        fake_db.turns.append({"session_id": session_id, "user_message": user_message, "assistant_message": assistant_message})

    async def fake_run_retriever(query: str, _db, user_id: int, *, top_k: int, memory_context: dict[str, Any]):
        turn_count = len(memory_context.get("episodic") or [])
        return {
            "answer": f"user={user_id};turns={turn_count};query={query}",
            "chunks": [{"content": f"source for {query}", "report_id": "11", "rerank_score": 0.88}],
        }

    app.dependency_overrides[require_member] = override_member
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis

    try:
        with patch("api.v1.knowledge.preload_retriever_context", new=AsyncMock(side_effect=fake_preload)), \
             patch("api.v1.knowledge.record_retriever_turn", new=AsyncMock(side_effect=fake_record_turn)), \
             patch("api.v1.knowledge.run_retriever_agent", new=AsyncMock(side_effect=fake_run_retriever)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                first = await client.post(
                    "/api/v1/knowledge/query",
                    json={"query": "第一次提问", "top_k": 5, "session_id": "session-a"},
                )
                second = await client.post(
                    "/api/v1/knowledge/query",
                    json={"query": "第二次追问", "top_k": 5, "session_id": "session-a"},
                )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert "turns=0" in first.json()["answer"]
    assert "turns=1" in second.json()["answer"]
    assert first.json()["sources"][0]["report_id"] == "11"
    assert len(fake_db.turns) == 2
    assert fake_db.turns[0]["user_message"] == "第一次提问"
    assert fake_db.turns[1]["user_message"] == "第二次追问"
    assert fake_db.commits == 2
