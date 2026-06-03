"""Token accounting helper tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.memory_manager import _actual_token_total, _estimated_token_total  # noqa: E402


class TokenAccountingTest(unittest.TestCase):
    def test_actual_token_total_prefers_explicit_total(self) -> None:
        self.assertEqual(
            _actual_token_total(
                {
                    "total": 42,
                    "breakdown": {"planner": {"total": 10}},
                }
            ),
            42,
        )

    def test_actual_token_total_falls_back_to_breakdown(self) -> None:
        self.assertEqual(
            _actual_token_total(
                {
                    "breakdown": {
                        "planner": {"total": 10},
                        "retrieve": {"total": 20},
                    }
                }
            ),
            30,
        )

    def test_estimated_token_total_reads_state_then_topic_config_then_actual(self) -> None:
        self.assertEqual(_estimated_token_total({"estimated_token_usage": {"total": 100}}), 100)
        self.assertEqual(_estimated_token_total({"topic_config": {"token_estimate": 80}}), 80)
        self.assertEqual(
            _estimated_token_total({"token_usage": {"breakdown": {"planner": {"total": 25}}}}),
            25,
        )


if __name__ == "__main__":
    unittest.main()
