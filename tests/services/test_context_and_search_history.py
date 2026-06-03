"""Context manager and search-history utility tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agents.retriever import _rrf_fuse  # noqa: E402
from services.context_manager import ContextItem, build_context, textrank_summary  # noqa: E402
from services.search_history_service import _actual_search_mode, _extract_actual_sources  # noqa: E402


class ContextAndSearchHistoryTest(unittest.TestCase):
    def test_context_manager_preserves_p0_and_trims_low_priority(self) -> None:
        long_text = "低优先级内容。" * 3000
        result = build_context(
            [
                ContextItem(priority="P0", name="current_user_input", content="当前问题", can_trim=False),
                ContextItem(priority="P5", name="agent_trace", content=long_text),
            ],
            scenario="tool_call",
        )
        self.assertIn("当前问题", result["context"])
        self.assertLess(result["token_estimate"], 4096)
        self.assertTrue(result["actions"])

    def test_textrank_summary_keeps_representative_sentences(self) -> None:
        text = "苹果很好。香蕉一般。苹果适合做派。苹果也适合榨汁。"
        summary = textrank_summary(text)
        self.assertIn("苹果", summary)
        self.assertLessEqual(len(summary), len(text))

    def test_rrf_fuses_keyword_and_vector_results(self) -> None:
        keyword = [
            SimpleNamespace(id=1, content="A", report_id=10, score=0.9),
            SimpleNamespace(id=2, content="B", report_id=10, score=0.8),
        ]
        vector = [
            SimpleNamespace(id=2, content="B", report_id=10, score=0.7),
            SimpleNamespace(id=3, content="C", report_id=11, score=0.6),
        ]
        fused = _rrf_fuse(keyword, vector, rrf_k=60, limit=3)
        self.assertEqual(fused[0]["id"], "2")
        self.assertEqual(set(fused[0]["channels"]), {"keyword", "vector"})

    def test_search_history_detects_actual_sources_and_mode(self) -> None:
        raw = [
            {"url": "https://example.com/a", "kind": "search_api"},
            {"url": "https://docs.example.org/b", "kind": "crawler"},
        ]
        self.assertEqual(_actual_search_mode(raw, "api"), "mixed")
        self.assertEqual(_extract_actual_sources(raw, []), ["example.com", "docs.example.org"])


if __name__ == "__main__":
    unittest.main()
