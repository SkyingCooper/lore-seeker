"""约束接口 smoke tests。

这些测试不访问网络和数据库，只验证 Agent / Tool / Redis / DB contract 的基础
payload 能被当前 schema 接受，防止文档和运行时代码再次漂移。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agents.contracts import (  # noqa: E402
    validate_planner_to_searcher_task,
    validate_searcher_result,
    validate_worker_to_planner_task,
)
from agents.memory_manager import build_memory_manager_handoff  # noqa: E402
from constraint.validation.validator import (  # noqa: E402
    validate_db_contract,
    validate_redis_value,
    validate_tool_input,
    validate_tool_output,
)
from constraint.validation.middleware import _validate_route_body  # noqa: E402


class ContractSmokeTest(unittest.TestCase):
    def test_agent_contracts_accept_current_state_shape(self) -> None:
        state = {
            "user_id": "1",
            "task_id": "2",
            "query": "测试主题",
            "topic_config": {
                "search_mode": "mixed",
                "frequency": "once",
                "source_sites": ["https://example.com"],
            },
        }
        validate_worker_to_planner_task(state)
        validate_planner_to_searcher_task(state, {"search_queries": ["测试主题"]})
        validate_searcher_result(
            state,
            [{"title": "Example", "url": "https://example.com", "content": "content"}],
        )
        build_memory_manager_handoff(
            type(
                "Task",
                (),
                {
                    "id": 2,
                    "topic_id": 1,
                    "user_id": 1,
                    "query": "测试主题",
                    "source_sites": ["https://example.com"],
                    "search_mode": "mixed",
                    "frequency": "once",
                },
            )(),
            {"topic_config": state["topic_config"], "quality_score": 95, "organized_md": "# ok"},
            succeeded=True,
        )

    def test_storage_contracts_accept_runtime_payloads(self) -> None:
        validate_redis_value(
            {
                "task_id": "2",
                "user_id": "1",
                "query": "测试主题",
                "topic_config": {},
                "frequency": "biweekly",
                "status": "running",
                "started_at": "2026-06-02T00:00:00+00:00",
                "expected_subtask_count": 0,
            },
            "task_context",
        )
        validate_redis_value({"total": 0, "completed": 0, "failed": 0, "items": []}, "task_subtasks")
        validate_db_contract(
            "retrieve_knowledge",
            caller="retriever",
            operation="select",
            params={"user_id": 1, "query_embedding": [0.1], "query": "测试"},
        )

    def test_tool_contracts_accept_search_envelopes(self) -> None:
        tool_input = {
            "schema_version": "1.0",
            "contract_type": "tool.input",
            "tool_name": "search_api",
            "caller": "searcher",
            "input": {
                "kind": "search_api",
                "query": "测试",
                "source_sites": ["https://example.com"],
                "provider": "tavily",
                "max_results": 10,
            },
            "timeout_seconds": 30,
            "retry": {"max_attempts": 3, "backoff": "exponential"},
            "metadata": {},
        }
        validate_tool_input(tool_input)
        validate_tool_output(
            {
                "schema_version": "1.0",
                "contract_type": "tool.output",
                "tool_name": "search_api",
                "status": "succeeded",
                "data": {"results": []},
                "error": None,
                "metrics": {"duration_ms": 1, "retry_count": 0, "result_count": 0, "token_usage": None},
                "metadata": {},
            }
        )

    def test_http_route_contract_rejects_deprecated_target_sites(self) -> None:
        error = _validate_route_body(
            "/api/v1/search/start",
            "POST",
            b'{"query":"x","target_sites":["example.com"],"search_mode":"mixed"}',
        )
        self.assertIsNotNone(error)
        self.assertEqual(error["code"], "CONTRACT_FIELD_DEPRECATED")

    def test_http_route_contract_accepts_knowledge_query(self) -> None:
        error = _validate_route_body(
            "/api/v1/knowledge/query",
            "POST",
            b'{"query":"how to use lore seeker","top_k":5,"session_id":"default"}',
        )
        self.assertIsNone(error)

    def test_http_route_contract_rejects_invalid_report_evaluation(self) -> None:
        error = _validate_route_body(
            "/api/v1/reports/12/evaluate",
            "POST",
            b'{"satisfaction":"bad","notes":"x"}',
        )
        self.assertIsNotNone(error)
        self.assertEqual(error["code"], "CONTRACT_INVALID_SATISFACTION")

    def test_http_route_contract_rejects_empty_preferences_patch(self) -> None:
        error = _validate_route_body(
            "/api/v1/users/me/preferences",
            "PATCH",
            b'{"preferences":{}}',
        )
        self.assertIsNotNone(error)
        self.assertEqual(error["code"], "CONTRACT_INVALID_PREFERENCES")


if __name__ == "__main__":
    unittest.main()
