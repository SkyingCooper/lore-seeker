"""Pytest coverage for deterministic async agent state transitions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from agents import organizer, planner, retriever


@pytest.mark.asyncio
async def test_run_planner_agent_falls_back_to_original_query_when_model_returns_empty_queries() -> None:
    state = {
        "user_id": "1",
        "task_id": "2",
        "query": "多 agent 设计",
        "topic_config": {"search_mode": "mixed", "source_sites": ["https://example.com"]},
        "token_usage": {},
        "iteration": 0,
    }
    mocked_result = SimpleNamespace(
        output=planner.PlannerPlanOutput(
            search_queries=[],
            focus_areas=["架构"],
            expected_chapters=["执行流"],
            needs_decomposition=True,
        ),
        usage=SimpleNamespace(input_tokens=12, output_tokens=8),
    )

    with patch.object(planner, "get_prompt", return_value="system"), \
         patch.object(planner, "render_prompt", return_value="user"), \
         patch.object(planner, "build_agent_model", return_value="mock-model"), \
         patch.object(planner.PLANNER_PLAN_AGENT, "run", new=AsyncMock(return_value=mocked_result)):
        result = await planner.run_planner_agent(state)

    assert result["topic_config"]["_plan"]["search_queries"] == ["多 agent 设计"]
    assert result["topic_config"]["_plan"]["needs_decomposition"] is True
    assert result["token_usage"]["breakdown"]["planner"]["total"] == 20
    assert result["iteration"] == 0


@pytest.mark.asyncio
async def test_run_organizer_agent_keeps_cleaned_and_discarded_results_in_output_state() -> None:
    state = {
        "user_id": "1",
        "task_id": "3",
        "query": "检索报告",
        "raw_results": [{"title": "A", "url": "https://example.com", "content": "valid content"}],
        "quality_feedback": "",
        "token_usage": {},
    }
    processed = organizer.process_search_results(state["raw_results"])
    mocked_result = SimpleNamespace(
        output=organizer.OrganizerOutput(content_md="# 报告\n\n## 结论", toc=[]),
        usage=SimpleNamespace(input_tokens=10, output_tokens=6),
    )

    with patch.object(organizer, "get_prompt", return_value="system"), \
         patch.object(organizer, "render_prompt", return_value="user"), \
         patch.object(organizer, "build_agent_model", return_value="mock-model"), \
         patch.object(organizer, "process_search_results", return_value=processed), \
         patch.object(organizer.ORGANIZER_AGENT, "run", new=AsyncMock(return_value=mocked_result)):
        result = await organizer.run_organizer_agent(state)

    assert result["organized_md"].startswith("# 报告")
    assert result["cleaned_raw_results"] == processed.cleaned_results
    assert result["discarded_items"] == processed.discarded_items
    assert result["token_usage"]["breakdown"]["sort"]["total"] == 16


@pytest.mark.asyncio
async def test_run_retriever_agent_short_query_returns_clarification_without_hitting_retrieve() -> None:
    with patch.object(retriever, "retrieve", new=AsyncMock()) as mocked_retrieve:
        result = await retriever.run_retriever_agent("短", AsyncMock(), 99, top_k=5, memory_context={})

    mocked_retrieve.assert_not_awaited()
    assert result["chunks"] == []
    assert "不能确定" in result["answer"]
    assert result["intent"]["confidence"] < 0.6


@pytest.mark.asyncio
async def test_run_retriever_agent_merges_context_manager_usage_after_answer() -> None:
    chunks = [{"content": "answer body", "report_id": "1", "score": 0.9}]

    with patch.object(retriever, "_classify_intent", return_value={"intent": "knowledge_query", "confidence": 0.9}), \
         patch.object(retriever, "retrieve", new=AsyncMock(return_value=chunks)), \
         patch.object(
             retriever,
             "answer",
             new=AsyncMock(
                 return_value={
                     "answer": "ok",
                     "sources_used": [1],
                     "token_usage": {
                         "total": 5,
                         "breakdown": {
                             "search": {"input_tokens": 0, "output_tokens": 0, "total": 0},
                             "sort": {"input_tokens": 0, "output_tokens": 0, "total": 0},
                             "retrieve": {"input_tokens": 2, "output_tokens": 3, "total": 5},
                             "planner": {"input_tokens": 0, "output_tokens": 0, "total": 0},
                             "memory_manager": {"input_tokens": 0, "output_tokens": 0, "total": 0},
                             "context_manager": {"input_tokens": 0, "output_tokens": 0, "total": 0},
                         },
                         "model_used": {
                             "search": None,
                             "sort": None,
                             "retrieve": "qwen",
                             "planner": None,
                             "memory_manager": None,
                             "context_manager": None,
                         },
                     },
                     "context_token_estimate": 12,
                 }
             ),
         ):
        result = await retriever.run_retriever_agent(
            "这个主题的背景是什么？",
            AsyncMock(),
            7,
            top_k=5,
            memory_context={"semantic": [], "episodic": [], "preferences": []},
        )

    assert result["answer"] == "ok"
    assert result["chunks"] == chunks
    assert result["token_usage"]["breakdown"]["context_manager"]["total"] == 12
    assert result["token_usage"]["total"] == 17
