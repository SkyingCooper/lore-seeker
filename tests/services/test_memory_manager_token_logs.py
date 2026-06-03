"""Memory manager token accounting tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.memory_manager import _build_token_logs  # noqa: E402


class MemoryManagerTokenLogsTest(unittest.TestCase):
    def test_build_token_logs_splits_stage_breakdown(self) -> None:
        logs = _build_token_logs(
            user_id="1",
            task_id="2",
            estimated_before=300,
            starting_balance=1000,
            token_usage={
                "timestamp": "2026-06-03T00:00:00Z",
                "breakdown": {
                    "planner": {"input_tokens": 10, "output_tokens": 5, "total": 15},
                    "retrieve": {"input_tokens": 20, "output_tokens": 10, "total": 30},
                    "search": {"input_tokens": 0, "output_tokens": 0, "total": 0},
                },
                "model_used": {"planner": "qwen-plus", "retrieve": "qwen-turbo"},
            },
        )
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].stage, "planner")
        self.assertEqual(logs[0].provider, "aliyun")
        self.assertEqual(logs[1].balance_after, 955)


if __name__ == "__main__":
    unittest.main()
