"""任务成本/额度汇总工具。

本模块负责把搜索 API、爬虫、MCP 等非 token 资源消耗统一汇总为 reports.cost_usage
所需结构。与 token_usage 不同，这里记录的是美元估算成本、请求次数和额度消耗。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


COST_STAGES = ("search", "sort", "retrieve", "planner", "memory_manager", "context_manager")


def empty_cost_usage() -> dict[str, Any]:
    """返回 reports.cost_usage 的默认结构。"""

    return {
        "total_usd": 0.0,
        "breakdown": {
            stage: {
                "estimated_cost_usd": 0.0,
                "request_count": 0,
                "quota_consumed": 0,
                "quota_unit": None,
                "providers": {},
            }
            for stage in COST_STAGES
        },
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def merge_stage_cost(
    current: dict[str, Any] | None,
    *,
    stage: str,
    provider: str | None,
    estimated_cost_usd: float = 0.0,
    request_count: int = 0,
    quota_consumed: int = 0,
    quota_unit: str | None = None,
) -> dict[str, Any]:
    """把一个环节的成本/额度消耗合并到总结构。"""

    result = empty_cost_usage()
    if current:
        result["total_usd"] = float(current.get("total_usd") or 0.0)
        result["breakdown"].update(current.get("breakdown") or {})

    if stage not in result["breakdown"]:
        result["breakdown"][stage] = {
            "estimated_cost_usd": 0.0,
            "request_count": 0,
            "quota_consumed": 0,
            "quota_unit": None,
            "providers": {},
        }

    stage_item = result["breakdown"][stage]
    stage_item["estimated_cost_usd"] = round(
        float(stage_item.get("estimated_cost_usd") or 0.0) + float(estimated_cost_usd or 0.0),
        6,
    )
    stage_item["request_count"] = int(stage_item.get("request_count") or 0) + int(request_count or 0)
    stage_item["quota_consumed"] = int(stage_item.get("quota_consumed") or 0) + int(quota_consumed or 0)
    stage_item["quota_unit"] = quota_unit or stage_item.get("quota_unit")

    provider_key = provider or "unknown"
    providers = stage_item.setdefault("providers", {})
    provider_item = providers.setdefault(
        provider_key,
        {
            "estimated_cost_usd": 0.0,
            "request_count": 0,
            "quota_consumed": 0,
            "quota_unit": quota_unit,
        },
    )
    provider_item["estimated_cost_usd"] = round(
        float(provider_item.get("estimated_cost_usd") or 0.0) + float(estimated_cost_usd or 0.0),
        6,
    )
    provider_item["request_count"] = int(provider_item.get("request_count") or 0) + int(request_count or 0)
    provider_item["quota_consumed"] = int(provider_item.get("quota_consumed") or 0) + int(quota_consumed or 0)
    provider_item["quota_unit"] = quota_unit or provider_item.get("quota_unit")

    result["total_usd"] = round(
        sum(float(item.get("estimated_cost_usd") or 0.0) for item in result["breakdown"].values()),
        6,
    )
    result["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return result
