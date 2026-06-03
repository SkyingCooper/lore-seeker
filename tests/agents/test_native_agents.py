"""Native agent entry tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agents.planner import PlannerPlanOutput, PlannerQualityOutput, run_planner_agent, run_quality_check_agent  # noqa: E402
from agents.organizer import OrganizerOutput, run_organizer_agent  # noqa: E402
from agents.retriever import run_retriever_agent  # noqa: E402
from agents.searcher import run_searcher_agent  # noqa: E402


class NativeAgentEntryTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_planner_agent_returns_structured_plan(self) -> None:
        state = {
            "user_id": "1",
            "task_id": "2",
            "query": "测试主题",
            "topic_config": {"search_mode": "mixed", "source_sites": ["https://example.com"]},
            "token_usage": {},
            "iteration": 0,
        }
        mocked_result = SimpleNamespace(
            output=PlannerPlanOutput(search_queries=["测试主题"], focus_areas=["A"], expected_chapters=["B"]),
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        with patch("agents.planner.build_agent_model", return_value="mock-model"):
            with patch("agents.planner.PLANNER_PLAN_AGENT.run", new=AsyncMock(return_value=mocked_result)):
                result = await run_planner_agent(state)
        self.assertIn("_plan", result["topic_config"])
        self.assertEqual(result["topic_config"]["_plan"]["search_queries"], ["测试主题"])
        self.assertEqual(result["token_usage"]["breakdown"]["planner"]["total"], 15)

    async def test_run_quality_check_agent_returns_structured_score(self) -> None:
        state = {
            "user_id": "1",
            "task_id": "2",
            "organized_md": "# report",
            "token_usage": {},
            "iteration": 0,
        }
        mocked_result = SimpleNamespace(
            output=PlannerQualityOutput(score=92, feedback="ok", **{"pass": True}),
            usage=SimpleNamespace(input_tokens=8, output_tokens=4),
        )
        with patch("agents.planner.build_agent_model", return_value="mock-model"):
            with patch("agents.planner.PLANNER_QUALITY_AGENT.run", new=AsyncMock(return_value=mocked_result)):
                result = await run_quality_check_agent(state)
        self.assertEqual(result["quality_score"], 92)
        self.assertTrue(result["final"])

    async def test_run_organizer_agent_returns_markdown(self) -> None:
        state = {
            "user_id": "1",
            "task_id": "2",
            "query": "测试主题",
            "raw_results": [{"title": "A", "url": "https://example.com", "content": "hello"}],
            "quality_feedback": "",
            "token_usage": {},
        }
        mocked_result = SimpleNamespace(
            output=OrganizerOutput(content_md="# 标题\n\n## 一节", toc=[]),
            usage=SimpleNamespace(input_tokens=20, output_tokens=10),
        )
        with patch("agents.organizer.build_agent_model", return_value="mock-model"):
            with patch("agents.organizer.ORGANIZER_AGENT.run", new=AsyncMock(return_value=mocked_result)):
                result = await run_organizer_agent(state)
        self.assertTrue(result["organized_md"].startswith("# 标题"))
        self.assertGreater(result["token_usage"]["breakdown"]["sort"]["total"], 0)
        self.assertIn("cleaned_raw_results", result)
        self.assertIn("discarded_items", result)

    async def test_run_searcher_agent_uses_tools_and_dedupes(self) -> None:
        state = {
            "user_id": "1",
            "task_id": "2",
            "query": "测试主题",
            "topic_config": {
                "search_mode": "mixed",
                "source_sites": ["https://example.com"],
                "_plan": {"search_queries": ["测试主题"]},
            },
            "token_usage": {},
        }
        api_results = [{"title": "A", "url": "https://example.com/a", "content": "x"}]
        crawl_results = [
            {"title": "A", "url": "https://example.com/a", "content": "x"},
            {"title": "B", "url": "https://example.com/b", "content": "y"},
        ]
        with patch("agents.searcher.call_named_search_tool", new=AsyncMock(return_value=api_results)):
            with patch("agents.searcher.call_crawler_tool", new=AsyncMock(return_value=crawl_results)):
                result = await run_searcher_agent(state)
        self.assertEqual(len(result["raw_results"]), 2)

    async def test_run_retriever_agent_wraps_retrieve_and_answer(self) -> None:
        chunks = [{"content": "x", "report_id": "1", "score": 0.9}]
        with patch("agents.retriever.retrieve", new=AsyncMock(return_value=chunks)):
            with patch("agents.retriever.answer", new=AsyncMock(return_value={"answer": "ok", "token_usage": {}, "context_token_estimate": 10})):
                result = await run_retriever_agent("这个主题的完整背景是什么？", AsyncMock(), 1, top_k=5, memory_context={})
        self.assertEqual(result["answer"], "ok")
        self.assertEqual(result["chunks"], chunks)


if __name__ == "__main__":
    unittest.main()
