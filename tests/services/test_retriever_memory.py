"""Retriever memory service tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.retriever_memory import preload_retriever_context, record_retriever_turn  # noqa: E402


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def setex(self, key: str, _ttl: int, value: str):
        self.data[key] = value


class RetrieverMemoryTest(unittest.IsolatedAsyncioTestCase):
    async def test_preload_context_includes_preferences(self) -> None:
        redis = _FakeRedis()
        with patch("services.retriever_memory._load_episodic", new=AsyncMock(return_value=[{"content": "e1"}])):
            with patch("services.retriever_memory._load_semantic", new=AsyncMock(return_value=[{"title": "s1"}])):
                with patch("services.retriever_memory._load_preferences", new=AsyncMock(return_value=[{"key": "format", "value": "concise"}])):
                    context = await preload_retriever_context(AsyncMock(), redis, user_id=1, session_id="default")
        self.assertIn("preferences", context)
        self.assertEqual(context["preferences"][0]["key"], "format")

    async def test_record_turn_updates_context_and_preference_cache(self) -> None:
        redis = _FakeRedis()
        db = AsyncMock()
        with patch("services.retriever_memory.insert_episodic_log", new=AsyncMock()):
            with patch("services.retriever_memory.upsert_user_preference", new=AsyncMock()):
                with patch("services.retriever_memory._load_preferences", new=AsyncMock(return_value=[{"key": "response_preference", "value": "详细一点"}])):
                    await record_retriever_turn(
                        db,
                        redis,
                        user_id=1,
                        session_id="s1",
                        user_message="我希望详细一点",
                        assistant_message="好的",
                    )
        context = json.loads(redis.data["session:1:s1:context"])
        self.assertEqual(context[-2]["event_type"], "user_message")
        self.assertEqual(context[-1]["event_type"], "agent_response")
        preferences = json.loads(redis.data["user:1:preferences"])
        self.assertEqual(preferences[0]["value"], "详细一点")


if __name__ == "__main__":
    unittest.main()
