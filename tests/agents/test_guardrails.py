"""Agent guardrail hook tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agents.guardrails import (  # noqa: E402
    AgentOutputContext,
    AgentErrorContext,
    ModelRequestContext,
    AgentRunContext,
    ToolResultContext,
    ToolCallContext,
    after_run,
    after_tool_call,
    before_model_request,
    before_run,
    before_tool_call,
    on_tool_error,
    on_error,
    sanitize_payload,
    build_guarded_pydantic_agent,
)
from constraint.validation.validator import ContractValidationError  # noqa: E402
from services.memory_manager import _archive_guardrail_logs  # noqa: E402
from db.models import SearchTask  # noqa: E402


class GuardrailHookTest(unittest.TestCase):
    def test_before_run_allows_declared_responsibility_and_operation(self) -> None:
        decision = before_run(
            AgentRunContext(
                agent_name="planner",
                responsibility="task_planning",
                operation="decompose_task",
                state={"topic_config": {}, "quality_score": 0},
            )
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.alert_level, "none")

    def test_before_tool_call_rejects_denied_tool(self) -> None:
        with self.assertRaises(ContractValidationError):
            before_tool_call(
                ToolCallContext(
                    agent_name="planner",
                    tool_name="search_api",
                    operation="execute_search_api",
                    args={"query": "x"},
                )
            )

    def test_before_tool_call_allows_declared_tool(self) -> None:
        decision = before_tool_call(
            ToolCallContext(
                agent_name="searcher",
                tool_name="web_search",
                operation="execute_search_api",
                args={"query": "python"},
            )
        )
        self.assertTrue(decision.allowed)

    def test_before_model_request_allows_valid_request(self) -> None:
        decision = before_model_request(
            ModelRequestContext(
                agent_name="retriever",
                operation="generate_context_grounded_answer",
                model_provider="dashscope",
                temperature=0.3,
                prompt_chars=1200,
            )
        )
        self.assertTrue(decision.allowed)

    def test_after_run_sanitizes_output_payload(self) -> None:
        decision = after_run(
            AgentOutputContext(
                agent_name="memory_manager",
                operation="process_memory_handoff",
                result={"token": "secret", "summary": "ok"},
            )
        )
        self.assertEqual(decision.sanitized_payload["token"], "***")
        self.assertEqual(decision.sanitized_payload["summary"], "ok")

    def test_after_tool_call_sanitizes_sensitive_result(self) -> None:
        decision = after_tool_call(
            ToolResultContext(
                agent_name="searcher",
                tool_name="web_search",
                operation="execute_search_api",
                result={"authorization": "Bearer x", "items": [{"title": "A"}]},
            )
        )
        self.assertEqual(decision.sanitized_payload["authorization"], "***")
        self.assertEqual(decision.sanitized_payload["items"][0]["title"], "A")

    def test_on_error_returns_critical_decision(self) -> None:
        decision = on_error(
            AgentErrorContext(
                agent_name="searcher",
                stage="on_error",
                operation="execute_search_api",
                error_type="RuntimeError",
                message="boom",
                retryable=False,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.alert_level, "critical")

    def test_on_tool_error_returns_warning_for_retryable(self) -> None:
        decision = on_tool_error(
            AgentErrorContext(
                agent_name="searcher",
                stage="on_tool_error",
                operation="execute_search_api",
                error_type="TimeoutError",
                message="timeout",
                retryable=True,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.alert_level, "warning")

    def test_on_tool_error_returns_critical_for_non_retryable(self) -> None:
        decision = on_tool_error(
            AgentErrorContext(
                agent_name="searcher",
                stage="on_tool_error",
                operation="execute_search_api",
                error_type="Forbidden",
                message="403",
                retryable=False,
            )
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.alert_level, "critical")

    def test_before_run_rejects_sensitive_state_field(self) -> None:
        with self.assertRaises(ContractValidationError):
            before_run(
                AgentRunContext(
                    agent_name="planner",
                    responsibility="task_planning",
                    operation="decompose_task",
                    state={"api_key": "secret"},
                )
            )

    def test_sanitize_payload_masks_sensitive_values(self) -> None:
        sanitized = sanitize_payload(
            {
                "authorization": "Bearer abc",
                "nested": {"api_key": "secret", "normal": "ok"},
            }
        )
        self.assertEqual(sanitized["authorization"], "***")
        self.assertEqual(sanitized["nested"]["api_key"], "***")
        self.assertEqual(sanitized["nested"]["normal"], "ok")

    def test_build_guarded_pydantic_agent_sets_guardrail_metadata(self) -> None:
        agent = build_guarded_pydantic_agent("planner", instructions="x")
        self.assertEqual(agent.name, "planner_guarded_agent")
        self.assertEqual(agent._metadata["guardrails"], "backend/constraint/agent_contracts/agent_boundaries.yaml")

    def test_archive_guardrail_logs_only_warning_and_critical(self) -> None:
        fake_db = _FakeDB()
        task = SearchTask(id=7, user_id=9, topic_id=1, query="q", source_sites=[], search_mode="mixed", frequency="once", status="completed")
        logs = [
            {
                "timestamp": "2026-06-04T10:00:00Z",
                "agent": "searcher",
                "guardrail_decision": {
                    "stage": "before_tool_call",
                    "allowed": True,
                    "alert_level": "none",
                    "sanitized_payload": {"query": "ok"},
                },
            },
            {
                "timestamp": "2026-06-04T10:00:01Z",
                "agent": "searcher",
                "guardrail_decision": {
                    "stage": "on_tool_error",
                    "allowed": False,
                    "alert_level": "warning",
                    "reason": "Timeout",
                    "sanitized_payload": {"token": "***"},
                },
            },
            {
                "timestamp": "2026-06-04T10:00:02Z",
                "agent": "retriever",
                "guardrail_decision": {
                    "stage": "on_error",
                    "allowed": False,
                    "alert_level": "critical",
                    "reason": "Boom",
                    "sanitized_payload": {"authorization": "***"},
                },
            },
        ]
        _archive_guardrail_logs(fake_db, task=task, logs=logs, caller="memory_manager")
        self.assertEqual(len(fake_db.items), 2)
        self.assertEqual(fake_db.items[0].alert_level, "warning")
        self.assertEqual(fake_db.items[1].alert_level, "critical")


class _FakeDB:
    def __init__(self) -> None:
        self.items = []

    def add(self, item) -> None:
        self.items.append(item)


if __name__ == "__main__":
    unittest.main()
