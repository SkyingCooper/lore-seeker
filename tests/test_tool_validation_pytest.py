"""Pytest coverage for deterministic tool validation and adapter logic."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from constraint.validation.validator import ContractValidationError
from services import tool_adapter


def test_resolve_env_placeholders_recurses_nested_runtime_payload() -> None:
    with patch.dict(os.environ, {"TEST_SEARCH_TOKEN": "token-value"}, clear=False):
        resolved = tool_adapter._resolve_env_placeholders(
            {
                "headers": {"Authorization": "${TEST_SEARCH_TOKEN}"},
                "servers": ["${TEST_SEARCH_TOKEN}", "plain"],
            }
        )

    assert resolved["headers"]["Authorization"] == "token-value"
    assert resolved["servers"] == ["token-value", "plain"]


@pytest.mark.asyncio
async def test_call_search_api_tool_rejects_undeclared_caller() -> None:
    with pytest.raises(ContractValidationError):
        await tool_adapter.call_search_api_tool(
            caller="planner",
            query="forbidden",
            source_sites=["https://example.com"],
            task_id="11",
        )


@pytest.mark.asyncio
async def test_call_named_search_tool_returns_items_and_metadata_from_mocked_provider() -> None:
    results = [{"title": "LoreSeeker", "url": "https://example.com", "content": "hello"}]

    with patch.object(tool_adapter, "search_api", new=AsyncMock(return_value=results)):
        output = await tool_adapter.call_named_search_tool(
            tool_name="web_search",
            caller="searcher",
            query="LoreSeeker",
            source_sites=["https://example.com"],
            task_id="22",
            include_metadata=True,
        )

    assert output["items"] == results
    assert output["tool_output"]["status"] == "succeeded"
    assert output["tool_output"]["metadata"]["cost_usage"]["provider"] == "google"


def test_estimate_cost_usage_is_stable_for_zero_results() -> None:
    estimated = tool_adapter._estimate_cost_usage(
        {
            "cost": {"base_request_cost_usd": 0.005, "per_result_cost_usd": 0.001},
            "quota": {"quota_per_call": 2, "unit": "request"},
        },
        provider="google",
        result_count=0,
    )

    assert estimated["estimated_cost_usd"] == 0.005
    assert estimated["quota_consumed"] == 2
    assert estimated["result_count"] == 0
