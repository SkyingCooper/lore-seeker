"""统一约束校验器。

本模块集中加载 backend/constraint 下的 JSON Schema，并提供 Agent、Tool、Storage
交互数据的校验入口。调用方应在 Agent handoff、Tool 调用前后、Redis/DB 写入前使用
这些函数，避免跨模块数据结构漂移。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
except ImportError:  # pragma: no cover - dependency guard for minimal environments.
    Draft202012Validator = None  # type: ignore[assignment]
    JsonSchemaValidationError = Exception  # type: ignore[assignment]

try:
    import yaml
except ImportError:  # pragma: no cover - dependency guard for minimal environments.
    yaml = None  # type: ignore[assignment]


CONSTRAINT_ROOT = Path(__file__).resolve().parents[1]


class ContractValidationError(ValueError):
    """Raised when a payload does not satisfy a declared contract."""

    def __init__(self, contract_name: str, message: str, path: list[str] | None = None) -> None:
        self.contract_name = contract_name
        self.path = path or []
        location = ".".join(self.path) if self.path else "<root>"
        super().__init__(f"{contract_name} validation failed at {location}: {message}")


@lru_cache(maxsize=32)
def load_json_schema(relative_path: str) -> dict[str, Any]:
    """Load a JSON Schema file from backend/constraint."""

    schema_path = CONSTRAINT_ROOT / relative_path
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=16)
def load_yaml_contract(relative_path: str) -> dict[str, Any]:
    """Load a YAML contract file from backend/constraint."""

    if yaml is None:
        raise ContractValidationError(
            relative_path,
            "PyYAML is not installed; add PyYAML to backend/requirements.txt",
        )

    contract_path = CONSTRAINT_ROOT / relative_path
    with contract_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContractValidationError(relative_path, "YAML contract root must be an object")
    return data


def validate_json_schema(payload: Any, schema_relative_path: str, contract_name: str | None = None) -> Any:
    """Validate payload against a JSON Schema and return the original payload.

    The return value lets callers use this function inline before forwarding a payload.
    """

    if Draft202012Validator is None:
        raise ContractValidationError(
            contract_name or schema_relative_path,
            "jsonschema is not installed; add jsonschema to backend/requirements.txt",
        )

    schema = load_json_schema(schema_relative_path)
    validator = Draft202012Validator(schema)
    try:
        validator.validate(payload)
    except JsonSchemaValidationError as exc:
        raise ContractValidationError(
            contract_name or schema_relative_path,
            exc.message,
            [str(part) for part in exc.absolute_path],
        ) from exc
    return payload


def validate_agent_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a Planner -> Searcher or Worker -> Planner task contract."""

    return validate_json_schema(
        payload,
        "agent_contracts/schemas/task_schema.json",
        "agent.task",
    )


def validate_agent_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an Agent result handoff contract."""

    return validate_json_schema(
        payload,
        "agent_contracts/schemas/result_schema.json",
        "agent.result",
    )


def validate_agent_error(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an Agent error contract."""

    return validate_json_schema(
        payload,
        "agent_contracts/schemas/error_schema.json",
        "agent.error",
    )


def validate_tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an Agent -> Tool input contract."""

    return validate_json_schema(
        payload,
        "tool_contracts/schemas/tool_input_schema.json",
        "tool.input",
    )


def validate_tool_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a Tool -> Agent output contract."""

    return validate_json_schema(
        payload,
        "tool_contracts/schemas/tool_output_schema.json",
        "tool.output",
    )


def validate_redis_value(payload: Any, definition_name: str) -> Any:
    """Validate a Redis value against a named definition in the Redis data contract."""

    if Draft202012Validator is None:
        raise ContractValidationError(
            f"storage.redis.{definition_name}",
            "jsonschema is not installed; add jsonschema to backend/requirements.txt",
        )

    schema = load_json_schema("storage_contracts/redis/data_schema.json")
    if definition_name not in schema.get("definitions", {}):
        raise ContractValidationError(
            f"storage.redis.{definition_name}",
            "unknown Redis value definition",
        )

    validator = Draft202012Validator(
        {
            "$schema": schema.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
            "$defs": schema["definitions"],
            "$ref": f"#/$defs/{definition_name}",
        }
    )
    try:
        validator.validate(payload)
    except JsonSchemaValidationError as exc:
        raise ContractValidationError(
            f"storage.redis.{definition_name}",
            exc.message,
            [str(part) for part in exc.absolute_path],
        ) from exc
    return payload


def _agent_boundary(agent_name: str) -> dict[str, Any]:
    """Return the declared boundary for a known Agent."""

    contract = load_yaml_contract("agent_contracts/agent_boundaries.yaml")
    agents = contract.get("agents", {})
    if agent_name not in agents:
        raise ContractValidationError("agent.boundary", f"unknown agent: {agent_name}")
    return agents[agent_name]


def _permission_rank(permission_name: str) -> int:
    """Return the numeric rank of a permission level."""

    contract = load_yaml_contract("agent_contracts/agent_boundaries.yaml")
    permission_levels = contract.get("permission_levels", {})
    if permission_name not in permission_levels:
        raise ContractValidationError("agent.permission", f"unknown permission: {permission_name}")
    return int(permission_levels[permission_name]["rank"])


def _matches_contract_pattern(value: str, pattern: str) -> bool:
    """Match simple contract patterns such as task:{task_id}:context."""

    regex = re.escape(pattern)
    regex = re.sub(r"\\\{[^}]+\\\}", r"[^:]+", regex)
    return re.fullmatch(regex, value) is not None


def validate_agent_operation(
    agent_name: str,
    operation: str,
    *,
    tool_name: str | None = None,
    required_permission: str | None = None,
) -> dict[str, Any]:
    """Validate Agent capability and permission boundary before execution."""

    agent = _agent_boundary(agent_name)
    capabilities = agent.get("capabilities", {})

    if tool_name and tool_name in capabilities.get("denied_tools", []):
        raise ContractValidationError("agent.boundary", f"{agent_name} is denied to call tool: {tool_name}")
    if tool_name and tool_name not in capabilities.get("allowed_tools", []):
        raise ContractValidationError("agent.boundary", f"{agent_name} cannot call undeclared tool: {tool_name}")

    if operation in capabilities.get("denied_operations", []):
        raise ContractValidationError("agent.boundary", f"{agent_name} is denied to perform: {operation}")
    if operation not in capabilities.get("allowed_operations", []):
        raise ContractValidationError("agent.boundary", f"{agent_name} cannot perform undeclared operation: {operation}")

    permission = agent.get("permission", {})
    operation_permission = required_permission or permission.get("required_permission", {}).get(operation)
    if operation_permission and _permission_rank(operation_permission) > _permission_rank(permission["level"]):
        raise ContractValidationError(
            "agent.permission",
            f"{agent_name} requires {operation_permission} for {operation}, but only has {permission['level']}",
        )

    return agent


def validate_agent_responsibility(agent_name: str, responsibility: str) -> dict[str, Any]:
    """Validate that an Agent owns a responsibility before accepting work."""

    agent = _agent_boundary(agent_name)
    responsibilities = agent.get("responsibilities", {})
    if responsibility in responsibilities.get("responsible_for", []):
        return agent

    owner_hint = responsibilities.get("not_responsible", {}).get(responsibility, "orchestrator")
    raise ContractValidationError(
        "agent.responsibility",
        f"这不是 {agent_name} 的职责，请找 {owner_hint}。",
    )


def validate_agent_data_access(
    agent_name: str,
    *,
    state_field: str | None = None,
    redis_key: str | None = None,
    db_table: str | None = None,
    config_path: str | None = None,
    data_label: str | None = None,
) -> dict[str, Any]:
    """Validate Agent data boundary before reading or writing state/storage."""

    agent = _agent_boundary(agent_name)
    data_boundary = agent.get("data_boundary", {})

    if data_label and data_label in data_boundary.get("denied_data", []):
        raise ContractValidationError("agent.data_boundary", f"{agent_name} is denied to access: {data_label}")

    if state_field and state_field not in data_boundary.get("allowed_state", []):
        raise ContractValidationError("agent.data_boundary", f"{agent_name} cannot access state: {state_field}")

    if redis_key:
        allowed_patterns = data_boundary.get("allowed_redis_keys", [])
        if not any(_matches_contract_pattern(redis_key, pattern) for pattern in allowed_patterns):
            raise ContractValidationError("agent.data_boundary", f"{agent_name} cannot access Redis key: {redis_key}")

    if db_table and db_table not in data_boundary.get("allowed_db_tables", []):
        raise ContractValidationError("agent.data_boundary", f"{agent_name} cannot access DB table: {db_table}")

    if config_path and config_path not in data_boundary.get("allowed_config_paths", []):
        raise ContractValidationError("agent.data_boundary", f"{agent_name} cannot access config path: {config_path}")

    return agent


def validate_agent_lifecycle(
    agent_name: str,
    *,
    idle_seconds: int = 0,
    active_seconds: int = 0,
) -> dict[str, Any]:
    """Validate Agent lifecycle limits before continuing execution."""

    agent = _agent_boundary(agent_name)
    lifecycle = agent.get("lifecycle", {})
    if idle_seconds > int(lifecycle.get("max_idle_seconds", 0)):
        raise ContractValidationError(
            "agent.lifecycle",
            f"{agent_name} exceeded max_idle_seconds; apply {lifecycle.get('on_incomplete')}",
        )
    if active_seconds > int(lifecycle.get("max_active_seconds", 0)):
        raise ContractValidationError(
            "agent.lifecycle",
            f"{agent_name} exceeded max_active_seconds; apply {lifecycle.get('on_incomplete')}",
        )
    return agent
