# Agent 护栏设计

本文档定义 Lore Seeker 使用 Pydantic AI 构建 Agent 护栏的落地方式。护栏代码入口为 `backend/agents/guardrails.py`，边界数据来源为 `backend/constraint/agent_contracts/agent_boundaries.yaml`。

## 1. 护栏目标

### 背景

Planner、Searcher、Organizer、Retriever 会调用 LLM、Tool、Redis 和 DB。如果只依赖业务代码自觉检查，容易出现越权调用、参数漂移、敏感数据进入日志、错误无法降级和审计链断裂。

### 决策

Agent 运行链路必须经过统一护栏。护栏使用 Pydantic 模型校验 hook 入参，使用 Pydantic AI `Agent` 承载后续 Agent 化迁移的 metadata，并复用 `agent_boundaries.yaml` 的能力、数据、职责、权限和生命周期约束。

### 实现要点

| Hook | 执行时机 | 职责 |
|---|---|---|
| `before_run` | Agent 开始执行前 | 输入校验、职责校验、权限检查、生命周期检查 |
| `after_run` | Agent 执行完成后 | 输出过滤、脱敏、审计载荷生成 |
| `before_model_request` | 每次调用 LLM 前 | 模型调用权限、温度、prompt 长度校验 |
| `before_tool_call` | 工具执行前 | Tool 白名单、操作权限、参数校验 |
| `on_tool_error` | 工具出错时 | 错误分类、降级决策、审计 |
| `after_tool_call` | 工具执行后 | 结果校验、脱敏、审计载荷生成 |
| `on_error` | 任意错误发生时 | 全局错误处理、严重告警审计 |

### 验收标准

- Agent 节点不能绕过 `guardrails.py` 直接调用 LLM 或 Tool。
- Tool 调用前必须通过 `before_tool_call`。
- LLM 调用前必须通过 `before_model_request`。
- 错误必须通过 `on_tool_error` 或 `on_error` 形成结构化审计载荷。

## 2. Pydantic 模型

### 背景

护栏 hook 本身也需要结构化输入，不能继续传自由 dict。

### 决策

`backend/agents/guardrails.py` 中定义以下 Pydantic 模型：

| 模型 | 用途 |
|---|---|
| `AgentRunContext` | Agent 执行前上下文 |
| `ModelRequestContext` | LLM 请求上下文 |
| `ToolCallContext` | Tool 调用上下文 |
| `ToolResultContext` | Tool 返回上下文 |
| `AgentOutputContext` | Agent 输出上下文 |
| `AgentErrorContext` | Agent/Tool 错误上下文 |
| `GuardrailDecision` | 护栏检查结果 |

### 实现要点

- `AgentName` 限制为 `planner/searcher/organizer/retriever`。
- `GuardrailStage` 限制为 7 个固定 hook 名称。
- `temperature` 限制在 `0..2`。
- `prompt_chars` 限制在 `0..32000`。
- `sanitize_payload()` 递归过滤 `api_key/token/password/authorization/cookie/secret` 等敏感字段。

### 验收标准

- 新 hook 入参必须先建 Pydantic 模型。
- 新敏感字段必须加入 `SENSITIVE_KEYS`。
- 护栏返回必须是 `GuardrailDecision`。

## 3. 边界联动

### 背景

护栏不重新发明权限规则，而是消费已有 Agent 边界契约。

### 决策

护栏调用 `constraint.validation.validator` 中的边界校验函数：

- `validate_agent_responsibility()`
- `validate_agent_operation()`
- `validate_agent_data_access()`
- `validate_agent_lifecycle()`

### 实现要点

- `before_run` 校验职责、操作和生命周期。
- `before_model_request` 把 LLM 视为 `llm` tool 校验。
- `before_tool_call` 校验 tool 白名单、operation 白名单和 required permission。
- `after_run` 和 `after_tool_call` 负责二次校验和脱敏。

### 验收标准

- 调用未声明 operation 时拒绝并 warning。
- 调用 denied operation/tool 时拒绝并 critical。
- 生命周期超时后必须按 `lifecycle.on_incomplete` 处理。
- 跨职责转交仍必须通过 orchestrator。

## 4. 当前接入点

### 背景

现有 Agent 仍由 LangGraph 编排，Pydantic AI 先作为护栏与后续迁移承载，不直接替换 LangGraph。

### 决策

当前先在四个 Agent 节点接入统一 hook。

### 实现要点

| 文件 | 已接入 |
|---|---|
| `backend/agents/planner.py` | `before_run`、`before_model_request`、`after_run`、`on_error` |
| `backend/agents/searcher.py` | `before_run`、`before_tool_call`、`after_tool_call`、`on_tool_error`、`after_run`、`on_error` |
| `backend/agents/organizer.py` | `before_run`、`before_model_request`、`after_run`、`on_error` |
| `backend/agents/retriever.py` | `before_run`、`before_tool_call`、`after_tool_call`、`before_model_request`、`on_tool_error`、`after_run`、`on_error` |

`build_guarded_pydantic_agent()` 用于后续把 LangGraph 节点迁移为 Pydantic AI Agent 时复用同一套 metadata。

### 验收标准

- 四个 Agent 文件能独立 import，不触发循环导入。
- 后端通过 `python3 -m compileall -q backend`。
- 护栏函数可在 `.venv` 中直接调用。

## 5. 审计与迁移

### 背景

护栏决策既需要服务当次任务排障，也需要保留 warning / critical 级别的长期审计记录。LangGraph 节点后续也需要逐步迁移到 Pydantic AI Agent 原生运行方式，方便独立测试和复用。

### 决策

- `GuardrailDecision` 摘要写入 Redis 工作日志 `task:{task_id}:working_log`。
- warning / critical 级别审计归档到独立表 `log_guardrail`。
- LangGraph 节点逐步迁移到 Pydantic AI Agent 原生运行方式。
- 每个 hook 必须补单元测试。

### 实现要点

- Redis 工作日志只保存脱敏后的护栏摘要。
- `log_guardrail` 保存长期审计记录，不替代 `zr_working_sessions`。
- 单元测试覆盖允许、拒绝、严重告警和脱敏路径。
- 迁移期间，Pydantic AI Agent 和 LangGraph 节点必须复用同一套 contract 与 guardrail hook。

### 验收标准

- 每次护栏决策可在任务工作日志中追踪。
- warning / critical 审计可从 `log_guardrail` 按 `task_id`、`agent_name`、`alert_level` 查询。
- hook 单测覆盖 before_run、after_run、before_model_request、before_tool_call、after_tool_call、on_tool_error、on_error。
