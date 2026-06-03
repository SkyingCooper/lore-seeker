"""Organizer processing tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.organizer_processing import build_marked_html, process_search_results  # noqa: E402


class OrganizerProcessingTest(unittest.TestCase):
    def test_process_search_results_marks_low_quality_and_duplicate(self) -> None:
        raw_results = [
            {
                "title": "Official Docs",
                "url": "https://docs.python.org/3/library/asyncio.html",
                "content": "<html><body>asyncio lets you write concurrent code using async/await. ```python``` updated event loops tasks futures transports protocols subprocesses streams synchronization primitives queues and examples for production usage.</body></html>",
                "published_at": "2026-06-01T00:00:00Z",
            },
            {
                "title": "Official Docs mirror",
                "url": "https://mirror.example.com/asyncio",
                "content": "asyncio lets you write concurrent code using async await updated event loops tasks futures transports protocols subprocesses streams synchronization primitives queues and examples for production usage",
            },
            {
                "title": "Ad page",
                "url": "https://example.com/ad",
                "content": "广告 免责声明 copyright all rights reserved",
            },
        ]
        processed = process_search_results(raw_results)
        self.assertEqual(len(processed.cleaned_results), 1)
        self.assertEqual(len(processed.discarded_items), 2)
        reasons = {item["discard_reason"] for item in processed.discarded_items}
        self.assertIn("duplicate", reasons)
        self.assertTrue("boilerplate" in reasons or "too_short" in reasons)

    def test_build_marked_html_contains_diff_tags(self) -> None:
        old = "Lore Seeker supports planner and searcher"
        new = "Lore Seeker supports planner searcher and organizer"
        marked = build_marked_html(new, old)
        self.assertIn("<del>", marked)
        self.assertTrue('class="added"' in marked or 'class="modified"' in marked)

    def test_build_marked_html_prefers_paragraph_level_diff(self) -> None:
        old = "第一段内容\n\n第二段原始内容"
        new = "第一段内容\n\n第二段修改后的内容"
        marked = build_marked_html(new, old)
        self.assertIn("<p>", marked)
        self.assertIn('class="modified"', marked)


if __name__ == "__main__":
    unittest.main()
