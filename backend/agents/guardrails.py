"""Agent 护栏：统一封装 Pydantic AI 运行期约束。

本模块把 Agent 执行、LLM 请求、Tool 调用、错误处理和审计事件收敛到一组
Pydantic 模型与 hook 函数中。业务 Agent 不应绕过这些 hook 直接调用模型或工具。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_ai import Agent as PydanticAIAgent

from constraint.validation.validator import (
    ContractValidationError,
    validate_agent_data_access,
    validate_agent_lifecycle,
    validate_agent_operation,
    validate_agent_responsibility,
)


AgentName = Literal["planner", "searcher", "organizer", "retriever"]
GuardrailStage = Literal[
    "before_run",
    "after_run",
    "before_model_request",
    "before_tool_call",
    "on_tool_error",
    "after_tool_call",
    "on_error",
]

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}


class GuardrailDecision(BaseModel):
    """单次护栏检查的结构化结果。"""

    allowed: bool
    stage: GuardrailStage
    agent_name: AgentName
    reason: str = ""
    alert_level: Literal["none", "warning", "critical"] = "none"
    sanitized_payload: dict[str, Any] = Field(default_factory=dict)


class AgentRunContext(BaseModel):
    """Agent 开始执行前的输入上下文。"""

    agent_name: AgentName
    responsibility: str
    operation: str
    user_id: str | int | None = None
    task_id: str | int | None = None
    idle_seconds: int = 0
    active_seconds: int = 0
    state: dict[str, Any] = Field(default_factory=dict)

    @field_validator("responsibility", "operation")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("value must not be empty")
        return value


class ModelRequestContext(BaseModel):
    """LLM 调用前的参数上下文。"""

    agent_name: AgentName
    operation: str
    model_provider: str = "default"
    temperature: float = Field(ge=0, le=2)
    prompt_chars: int = Field(ge=0, le=32000)


class ToolCallContext(BaseModel):
    """Tool 调用前的参数上下文。"""

    agent_name: AgentName
    tool_name: str
    operation: str
    args: dict[str, Any] = Field(default_factory=dict)
    required_permission: str | None = None


class ToolResultContext(BaseModel):
    """Tool 调用后的结果上下文。"""

    agent_name: AgentName
    tool_name: str
    operation: str
    result: Any = None


class AgentOutputContext(BaseModel):
    """Agent 执行完成后的输出上下文。"""

    agent_name: AgentName
    operation: str
    result: dict[str, Any] = Field(default_factory=dict)


class AgentErrorContext(BaseModel):
    """Agent 或 Tool 出错时的统一错误上下文。"""

    agent_name: AgentName
    stage: GuardrailStage
    operation: str
    error_type: str
    message: str
    retryable: bool = False


def build_guarded_pydantic_agent(agent_name: AgentName, instructions: str = "") -> PydanticAIAgent:
    """Create a Pydantic AI Agent carrying guardrail metadata.

    当前业务链路仍由 LangGraph 编排；该工厂用于后续把节点切换到 Pydantic AI Agent
    时复用同一套边界声明和 metadata。
    """

    return PydanticAIAgent(
        model=None,
        name=f"{agent_name}_guarded_agent",
        instructions=instructions,
        defer_model_check=True,
        metadata={"guardrails": "backend/constraint/agent_contracts/agent_boundaries.yaml"},
    )


def sanitize_payload(value: Any) -> Any:
    """Recursively remove sensitive values before logging or returning hook payloads."""

    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS or any(part in key.lower() for part in SENSITIVE_KEYS):
                sanitized[str(key)] = "***"
            else:
                sanitized[str(key)] = sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def _decision(
    *,
    allowed: bool,
    stage: GuardrailStage,
    agent_name: AgentName,
    reason: str = "",
    alert_level: Literal["none", "warning", "critical"] = "none",
    payload: Any = None,
) -> GuardrailDecision:
    sanitized = sanitize_payload(payload if isinstance(payload, dict) else {"value": payload})
    return GuardrailDecision(
        allowed=allowed,
        stage=stage,
        agent_name=agent_name,
        reason=reason,
        alert_level=alert_level,
        sanitized_payload=sanitized,
    )


def before_run(context: AgentRunContext) -> GuardrailDecision:
    """Agent 开始执行前：输入校验、职责校验、权限校验、生命周期校验。"""

    validate_agent_responsibility(context.agent_name, context.responsibility)
    validate_agent_operation(context.agent_name, context.operation)
    validate_agent_lifecycle(
        context.agent_name,
        idle_seconds=context.idle_seconds,
        active_seconds=context.active_seconds,
    )
    for key in context.state:
        if key.startswith("_"):
            continue
        try:
            validate_agent_data_access(context.agent_name, state_field=key)
        except ContractValidationError:
            # LangGraph state 会带一些跨节点字段；这里仅拦截明确禁止数据。
            if key in {".env", "api_key", "password", "token", "authorization"}:
                raise
    return _decision(stage="before_run", agent_name=context.agent_name, allowed=True, payload=context.state)


def after_run(context: AgentOutputContext) -> GuardrailDecision:
    """Agent 执行完成后：输出过滤、脱敏和审计载荷生成。"""

    validate_agent_operation(context.agent_name, context.operation)
    return _decision(stage="after_run", agent_name=context.agent_name, allowed=True, payload=context.result)


def before_model_request(context: ModelRequestContext) -> GuardrailDecision:
    """每次调用 LLM 前：权限、参数和请求体长度校验。"""

    validate_agent_operation(context.agent_name, context.operation, tool_name="llm")
    return _decision(stage="before_model_request", agent_name=context.agent_name, allowed=True, payload=context.model_dump())


def before_tool_call(context: ToolCallContext) -> GuardrailDecision:
    """工具执行前：Tool 白名单、操作权限和参数校验。"""

    validate_agent_operation(
        context.agent_name,
        context.operation,
        tool_name=context.tool_name,
        required_permission=context.required_permission,
    )
    return _decision(stage="before_tool_call", agent_name=context.agent_name, allowed=True, payload=context.args)


def after_tool_call(context: ToolResultContext) -> GuardrailDecision:
    """工具执行后：结果校验、脱敏和审计载荷生成。"""

    validate_agent_operation(context.agent_name, context.operation, tool_name=context.tool_name)
    payload = context.result if isinstance(context.result, dict) else {"result": context.result}
    return _decision(stage="after_tool_call", agent_name=context.agent_name, allowed=True, payload=payload)


def on_tool_error(context: AgentErrorContext) -> GuardrailDecision:
    """工具出错时：统一错误降级入口。"""

    return _decision(
        stage="on_tool_error",
        agent_name=context.agent_name,
        allowed=False,
        reason=f"{context.error_type}: {context.message}",
        alert_level="warning" if context.retryable else "critical",
        payload=context.model_dump(),
    )


def on_error(context: AgentErrorContext) -> GuardrailDecision:
    """任何错误发生时：全局错误处理和审计入口。"""

    return _decision(
        stage="on_error",
        agent_name=context.agent_name,
        allowed=False,
        reason=f"{context.error_type}: {context.message}",
        alert_level="critical",
        payload=context.model_dump(),
    )
