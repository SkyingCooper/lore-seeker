"""Memory manager subagent tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agents.memory_manager import (  # noqa: E402
    build_memory_manager_handoff,
    run_memory_manager_agent,
)


class MemoryManagerAgentTest(unittest.IsolatedAsyncioTestCase):
    def _task(self) -> SimpleNamespace:
        return SimpleNamespace(
            id=7,
            topic_id=3,
            user_id=11,
            query="测试主题",
            source_sites=["https://example.com"],
            search_mode="mixed",
            frequency="once",
        )

    def test_build_memory_manager_handoff_uses_planner_to_agent_contract(self) -> None:
        payload = build_memory_manager_handoff(
            self._task(),
            {
                "topic_config": {"keywords": ["测试主题"], "description": "desc"},
                "quality_score": 96,
                "organized_md": "# report",
                "used_skill_ids": [1, "2", "bad"],
                "token_usage": {"breakdown": {"memory_manager": {"total": 12}}},
            },
            succeeded=True,
        )
        self.assertEqual(payload["routing"]["from_agent"], "planner")
        self.assertEqual(payload["routing"]["to_agent"], "memory_manager")
        self.assertTrue(payload["extensions"]["memory_manager"]["extract_llm_memories"])
        self.assertEqual(payload["extensions"]["memory_manager"]["used_skill_ids"], [1, 2])

    async def test_run_memory_manager_agent_executes_service_and_returns_result_contract(self) -> None:
        session = SimpleNamespace(id=99)
        with patch("agents.memory_manager.run_task_memory_manager", new=AsyncMock(return_value=session)) as mocked_run:
            with patch("agents.memory_manager.append_log", new=AsyncMock()) as mocked_log:
                result = await run_memory_manager_agent(
                    AsyncMock(),
                    AsyncMock(),
                    task=self._task(),
                    final_state={
                        "topic_config": {"keywords": ["测试主题"]},
                        "quality_score": 97,
                        "organized_md": "# report",
                        "token_usage": {"breakdown": {"memory_manager": {"total": 15}}},
                    },
                    succeeded=True,
                )
        mocked_run.assert_awaited_once()
        self.assertEqual(result["producer_agent"], "memory_manager")
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["metadata"]["working_session_id"], 99)
        self.assertEqual(mocked_log.await_count, 2)


if __name__ == "__main__":
    unittest.main()
