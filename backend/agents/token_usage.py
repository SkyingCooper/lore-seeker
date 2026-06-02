"""Agent token 用量汇总工具。

本模块从 LangChain 模型响应中提取 provider 返回的 token usage，并按任务环节合并
为 reports.token_usage 所需结构。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


TOKEN_STAGES = ("search", "sort", "retrieve", "planner", "memory_manager", "context_manager")


def empty_token_usage() -> dict[str, Any]:
    """返回 reports.token_usage 的默认结构。"""

    return {
        "total": 0,
        "breakdown": {
            stage: {"input_tokens": 0, "output_tokens": 0, "total": 0}
            for stage in TOKEN_STAGES
        },
        "model_used": {stage: None for stage in TOKEN_STAGES},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def usage_from_response(response: Any) -> dict[str, int]:
    """从 LangChain response 提取 provider tokenizer 返回的 token usage。"""

    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total": total_tokens,
        }

    metadata = getattr(response, "response_metadata", None)
    token_usage = metadata.get("token_usage") if isinstance(metadata, dict) else None
    if isinstance(token_usage, dict):
        input_tokens = int(
            token_usage.get("prompt_tokens")
            or token_usage.get("input_tokens")
            or 0
        )
        output_tokens = int(
            token_usage.get("completion_tokens")
            or token_usage.get("output_tokens")
            or 0
        )
        total_tokens = int(token_usage.get("total_tokens") or input_tokens + output_tokens)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total": total_tokens,
        }

    return {"input_tokens": 0, "output_tokens": 0, "total": 0}


def merge_stage_usage(
    current: dict[str, Any] | None,
    *,
    stage: str,
    usage: dict[str, int],
    model: str | None,
) -> dict[str, Any]:
    """把一个环节的 token usage 合并到总结构。"""

    result = empty_token_usage()
    if current:
        result["total"] = int(current.get("total") or 0)
        result["breakdown"].update(current.get("breakdown") or {})
        result["model_used"].update(current.get("model_used") or {})

    if stage not in result["breakdown"]:
        result["breakdown"][stage] = {"input_tokens": 0, "output_tokens": 0, "total": 0}

    stage_usage = result["breakdown"][stage]
    stage_usage["input_tokens"] = int(stage_usage.get("input_tokens") or 0) + int(usage.get("input_tokens") or 0)
    stage_usage["output_tokens"] = int(stage_usage.get("output_tokens") or 0) + int(usage.get("output_tokens") or 0)
    stage_usage["total"] = int(stage_usage.get("total") or 0) + int(usage.get("total") or 0)
    result["model_used"][stage] = model or result["model_used"].get(stage)
    result["total"] = sum(int(item.get("total") or 0) for item in result["breakdown"].values())
    result["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return result
