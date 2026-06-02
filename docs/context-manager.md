# 上下文窗口管理设计

## 1. 模块职责

### 背景

多 Agent 系统会在 Agent 交互、Tool / MCP 调用、Redis/DB 读写和 LLM 请求前不断拼接上下文。如果没有统一的上下文窗口管理，prompt 会因为冗余信息、历史对话、工具结果和 Agent 中间过程而超出模型 token 限制，导致请求失败、关键信息被截断或低优先级内容挤占核心输入。

### 决策

独立设计 Context Manager，负责在所有需要塞入 prompt 的场景中组织上下文、计算 token、按优先级裁剪、摘要和压缩。Context Manager 不负责生成业务回答，只负责把可用上下文整理成符合模型窗口限制的 prompt 输入。

配置文件：

- `config/context_manager.yaml`

适用场景：

- Agent 之间交互。
- Tool / MCP 调用。
- Redis 交互。
- DB 交互。
- LLM 请求前的 prompt 构造。

### 实现要点

- 所有进入 prompt 的内容都必须先标记优先级。
- 所有场景都必须使用对应的 token 上限和裁剪阈值。
- 上下文超限时先裁剪，再摘要，再语义压缩。
- 极端情况下仍然超限时，向 Planner 告警并携带当前状态。

### 验收标准

- 用户当前问题和系统约束不会被裁剪。
- Tool、Redis、DB 结果进入 prompt 前经过 token 预算检查。
- 超限处理有可追踪的裁剪、摘要和压缩记录。

## 2. Prompt 注入场景

### 背景

上下文不是只在最终回答时使用。Agent handoff、Tool 调用、存储交互和 LLM 请求都需要构造局部 prompt 或上下文载荷。

### 决策

Context Manager 统一负责以下核心场景的上下文注入。

### 实现要点

0. 新任务开始首次载入

0.1 触发场景：

- Planner 接收新任务并开始规划前。
- 周期任务被 Celery 触发并创建新执行实例前。

0.2 如果存在可用 Skill，首次只载入第一阶段信息：

- `skill_id`
- `title`
- `desc`

0.3 首次载入不加载完整 `content` 和 `citation`，只有 Planner 判断某个 Skill 可能命中后，才按需进入第二阶段加载完整 SOP。

0.4 如果存在当前用户偏好，首次载入 `zr_user_preferences` 中与任务规划相关的偏好。

0.5 必须避免：

- 一开始就加载完整 Skill SOP。
- 加载其他用户的偏好或 Skill。
- 把低置信度隐式偏好覆盖用户本次明确输入。

1. Agent 之间交互

1.1 触发场景：

- Planner 将结构化任务交给 Searcher。
- Searcher 将搜索结果交给 Organizer。
- Organizer 将报告和评分交回 Planner。
- Retriever 需要基于上下文生成回答。

1.2 必须注入：

- 用户当前问题或任务。
- 当前 Agent 的职责边界。
- 当前步骤所需输入。
- 上一 Agent 的结构化输出。
- 必要的工作状态。

1.3 必须避免：

- 上一 Agent 的冗余思考过程。
- 与当前步骤无关的历史对话。
- 已经落库且可按 ID 反查的大段详情。

2. Tool / MCP 调用

2.1 触发场景：

- 搜索 Tool 调用。
- 爬虫 Tool 调用。
- Embedding / Rerank / LLM Tool 调用。
- MCP 工具调用。

2.2 必须注入：

- Tool 名称和操作目标。
- 参数 schema。
- 当前任务或查询的必要字段。
- Tool 调用约束。

2.3 必须避免：

- 与 Tool 参数无关的 Agent 对话历史。
- 敏感信息，例如 token、cookie、password、authorization。
- 不需要传给 Tool 的完整工作日志。

3. Redis / DB 交互

3.1 触发场景：

- 写入 Redis 工作区。
- 读取 Retriever 会话上下文。
- 查询知识切片。
- 写入报告、记忆或搜索历史。

3.2 必须注入：

- Storage contract 名称。
- Key / table / query contract。
- 当前 user_id 或 ownership join 约束。
- 必要输入字段。

3.3 必须避免：

- 绕过 contract 的自由 JSON。
- 无用户隔离的查询上下文。
- 大段原文结果重复注入。

### 验收标准

- 每次 Agent handoff、Tool 调用和 Storage 交互都能说明使用了哪个上下文场景。
- 上下文内容和场景配置一致。
- 敏感字段不会进入 prompt。

## 3. 优先级策略

### 背景

上下文超长时不能简单从头截断，否则可能删除用户当前问题或系统约束。必须先给内容分级，再按优先级保留。

### 决策

上下文分为 P0 到 P5 六级。P0 和 P1 绝不裁剪；P2 到 P5 根据超限情况依次裁剪、摘要或压缩。

### 实现要点

| 优先级 | 内容类型 | 示例 | 裁剪规则 |
|---|---|---|---|
| P0 | 用户当前问题 | 用户本次输入 | 绝不裁剪 |
| P1 | 系统指令 | 角色设定、任务目标、约束条件 | 绝不裁剪 |
| P2 | Tool / Storage 调用结果 | 搜索结果、数据库查询结果、Redis 状态 | 可摘要 |
| P3 | 相关记忆 | 用户偏好、Skill 第一阶段信息、语义记忆、情景记忆 | 可裁剪 |
| P4 | 历史对话 | 之前轮次的对话记录 | 可摘要 / 裁剪 |
| P5 | Agent 中间过程 | “我正在计划...”这类中间输出 | 优先裁剪 |

处理顺序：

1. 按优先级 P0 到 P5 依次塞入。
2. 每塞入一条，检查 token 计数。
3. 如果超过阈值，例如 `max_tokens * trim_threshold`，触发裁剪。
4. 裁剪从 P5 开始，逐步向高优先级裁剪。
5. 如果裁到 P2 仍然超限，触发摘要或压缩。

### 验收标准

- P0 和 P1 不会被裁剪。
- P5 优先被删除。
- P2 在被压缩前必须先尝试摘要。

## 4. 超长处理流程

### 背景

上下文超限可能来自工具结果过大、历史对话过多、语义记忆过多或 Agent 中间过程污染。需要有确定的降级顺序。

### 决策

超长处理顺序固定为：裁剪无关内容 -> TextRank 摘要 -> 语义压缩 -> 告警 Planner。

### 实现要点

1. 去除无关内容

1.1 优先删除 P5。

1.2 删除与当前问题无关的历史对话。

1.3 删除前面 Agent 的思考过程和中间输出。

1.4 保留结构化结果、ID、摘要和必要状态。

2. TextRank 摘要

2.1 如果裁剪后仍然超长，使用本地 TextRank 算法进行摘要。

2.2 默认摘要目标长度为原文的 `30%`。

2.3 默认摘要句数：

- 最少 2 句。
- 最多 5 句。

2.4 适用对象：

- P2 Tool / Storage 调用结果。
- P4 历史对话。
- 部分 P3 记忆内容。

3. 语义压缩

3.1 如果摘要后仍然超长，进入规则式语义压缩。

3.2 默认压缩目标长度为原文的 `15%`。

3.3 语义压缩必须保留：

- 用户当前问题。
- 系统约束。
- 关键事实。
- 关键 ID。
- 错误状态。
- 必要的来源引用。

4. 告警 Planner

4.1 如果语义压缩后仍然超长，将告警信息和当前状态转交 Planner。

4.2 告警内容必须包含：

- 场景名称。
- 当前 token 数。
- max_tokens。
- 已裁剪内容类型。
- 已摘要内容类型。
- 是否执行语义压缩。
- 仍然超限的原因。

### 验收标准

- 超限处理按固定顺序执行。
- 每次裁剪、摘要、压缩都有审计记录。
- 仍超限时不继续强行调用 LLM。

## 5. 配置参数

### 背景

不同场景能承受的 token 上限不同。Agent 交互可以保留更多上下文，Tool 和 Storage 调用应该更保守。

### 决策

上下文管理参数独立放入 `config/context_manager.yaml`，由后续 Context Manager 服务统一读取。

### 实现要点

默认配置：

```yaml
context_manager:
  default_max_tokens: 8192
  trim_threshold: 0.8
  scenarios:
    agent_communication:
      max_tokens: 8192
      trim_threshold: 0.8
    tool_call:
      max_tokens: 4096
      trim_threshold: 0.7
    storage_interaction:
      max_tokens: 4096
      trim_threshold: 0.7
    db_interaction:
      max_tokens: 4096
      trim_threshold: 0.7
    task_start_initial_load:
      max_tokens: 4096
      trim_threshold: 0.7
      include_skill_stage_one: true
      include_user_preferences: true
      skill_stage_one_fields: ["id", "title", "desc"]
  summarizer:
    method: "textrank"
    implementation: "local"
    target_ratio: 0.3
    min_sentences: 2
    max_sentences: 5
  compressor:
    method: "semantic"
    implementation: "rule_based"
    target_ratio: 0.15
  token_counter:
    method: "provider_tokenizer"
```

字段说明：

| 字段 | 说明 |
|---|---|
| `default_max_tokens` | 默认模型 token 上限 |
| `trim_threshold` | 触发裁剪的比例 |
| `scenarios.agent_communication` | Agent 之间交互配置 |
| `scenarios.tool_call` | Tool / MCP 调用配置 |
| `scenarios.storage_interaction` | Redis / DB 交互配置 |
| `scenarios.task_start_initial_load` | 新任务开始首次载入配置 |
| `summarizer.method` | 摘要方法：`textrank / tfidf / lsa` |
| `summarizer.implementation` | 摘要实现方式，当前固定为本地算法 |
| `summarizer.target_ratio` | 摘要目标长度比例 |
| `compressor.method` | 压缩方法：`semantic / truncate` |
| `compressor.implementation` | 语义压缩实现方式，当前固定为规则压缩 |
| `compressor.target_ratio` | 压缩目标长度比例 |
| `token_counter.method` | token 计数器，当前固定为模型 provider 自带 tokenizer |

### 验收标准

- 修改上下文窗口参数不需要改 Agent 代码。
- Tool 和 Storage 场景默认比 Agent 交互更保守。
- 配置文件中的场景名必须和 Context Manager 调用场景一致。

## 6. 已确认实现约束

1. token 计数器使用模型 provider 自带 tokenizer。
2. TextRank 由本地算法实现，不作为独立 summarizer tool。
3. 语义压缩目前使用规则压缩，不调用小模型。
4. 新任务开始首次载入只加载 Skill 第一阶段信息和用户偏好。
