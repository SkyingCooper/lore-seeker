"""LangGraph integration tests for node routing and state transitions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agents import graph as graph_module


@pytest.mark.asyncio
async def test_langgraph_routes_retry_then_done_and_persists_state_updates() -> None:
    route: list[str] = []

    async def fake_planner_node(state):
        route.append("planner")
        return {"topic_config": {**state["topic_config"], "_plan": {"search_queries": [state["query"]]}}, "iteration": 0}

    async def fake_searcher_node(state):
        route.append("searcher")
        return {
            "raw_results": [{"title": "A", "url": "https://example.com", "content": "content"}],
            "token_usage": {"total": 0, "breakdown": {}, "model_used": {}, "timestamp": "2026-06-04T00:00:00Z"},
            "cost_usage": {"total_usd": 0.0},
        }

    async def fake_organizer_node(state):
        route.append("organizer")
        version = "v2" if state.get("iteration", 0) >= 1 else "v1"
        return {"organized_md": f"# report-{version}", "toc": [{"title": version}]}

    async def fake_quality_check_node(state):
        route.append("quality_check")
        if state.get("iteration", 0) == 0:
            return {"quality_score": 55, "quality_feedback": "needs_retry", "final": False, "iteration": 1}
        return {"quality_score": 92, "quality_feedback": "ok", "final": True, "iteration": 2}

    def fake_should_retry(state):
        return "done" if state.get("final") else "retry"

    with patch("agents.planner.planner_node", fake_planner_node), \
         patch("agents.searcher.searcher_node", fake_searcher_node), \
         patch("agents.organizer.organizer_node", fake_organizer_node), \
         patch("agents.planner.quality_check_node", fake_quality_check_node), \
         patch("agents.planner.should_retry", fake_should_retry):
        compiled = graph_module.build_graph()
        final_state = await compiled.ainvoke(
            {
                "user_id": "1",
                "task_id": "2",
                "query": "测试 LangGraph 路由",
                "topic_config": {"search_mode": "mixed", "source_sites": ["https://example.com"]},
                "raw_results": [],
                "organized_md": "",
                "toc": [],
                "quality_score": 0,
                "quality_feedback": "",
                "token_usage": {},
                "cost_usage": {},
                "iteration": 0,
                "final": False,
            }
        )

    assert route == ["planner", "searcher", "organizer", "quality_check", "organizer", "quality_check"]
    assert final_state["final"] is True
    assert final_state["quality_score"] == 92
    assert final_state["organized_md"] == "# report-v2"
    assert final_state["raw_results"][0]["title"] == "A"
    assert final_state["topic_config"]["_plan"]["search_queries"] == ["测试 LangGraph 路由"]

