"""Agent guardrail hook tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from agents.guardrails import (  # noqa: E402
    AgentErrorContext,
    AgentRunContext,
    ToolCallContext,
    before_run,
    before_tool_call,
    on_error,
    sanitize_payload,
)
from constraint.validation.validator import ContractValidationError  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
