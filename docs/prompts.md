# Prompt 配置设计

本文档定义 Lore Seeker 提示词的集中管理规则。提示词属于配置，不允许散落在 Agent、Service 或 API 代码中。

## 1. 目录与职责

### 背景

Agent 提示词会持续调整。如果提示词硬编码在 Python 文件中，后续会导致版本追踪困难、复用困难和 prompt 变更污染业务代码。

### 决策

所有 LLM 提示词统一存放在项目根目录 `prompts/`，使用 Markdown 文件维护。

### 实现要点

```text
prompts/
├── README.md
├── planner.md
├── organizer.md
└── retriever.md
```

| 文件 | 职责 |
|---|---|
| `planner.md` | 任务规划和质量检查提示词 |
| `organizer.md` | Markdown 报告生成提示词 |
| `retriever.md` | 知识库问答提示词 |

### 验收标准

- Agent 文件中不再保存大段 system prompt。
- 新增提示词必须写入 `prompts/*.md`。
- 代码只通过 `core.prompt_loader` 读取提示词。

## 2. Prompt Block 格式

### 背景

Markdown 文件需要同时适合人阅读和机器加载。

### 决策

每个可加载提示词必须使用 `prompt-id` 注释块包裹。

### 实现要点

```md
## planner.plan.system

<!-- prompt-id: planner.plan.system -->
提示词正文
<!-- /prompt -->
```

命名规则：

- `agent.scene.role`
- `agent`：`planner`、`organizer`、`retriever`
- `scene`：业务场景，例如 `plan`、`quality_check`、`report`、`answer`
- `role`：`system` 或 `user`

模板变量使用 `$variable`，由 `string.Template` 渲染：

```md
<!-- prompt-id: planner.plan.user -->
查询：$query
主题配置：$topic_config
<!-- /prompt -->
```

### 验收标准

- `prompt-id` 全局唯一。
- JSON 示例中的 `{}` 不需要转义。
- 缺少变量时渲染失败，不能静默生成错误 prompt。

## 3. 加载方式

### 背景

业务代码需要稳定、统一的 prompt 加载入口。

### 决策

统一使用 `backend/core/prompt_loader.py`。

### 实现要点

核心函数：

- `load_prompts()`：加载 `prompts/*.md` 中所有 prompt block。
- `get_prompt(prompt_id)`：读取原始提示词。
- `render_prompt(prompt_id, **variables)`：渲染带变量提示词。

示例：

```python
system_prompt = get_prompt("planner.plan.system")
user_prompt = render_prompt("planner.plan.user", query=query, topic_config=topic_config)
```

### 验收标准

- 读取不存在的 `prompt-id` 必须抛出 `PromptNotFoundError`。
- 重复 `prompt-id` 必须抛出 `ValueError`。
- 所有 Agent LLM 调用前的 `prompt_chars` 使用渲染后的提示词长度计算。

## 4. 当前接入点

### 背景

当前需要先迁移已有硬编码提示词。

### 决策

已迁移以下 Agent：

| Agent | Prompt ID |
|---|---|
| Planner | `planner.plan.system`、`planner.plan.user` |
| Planner | `planner.quality_check.system`、`planner.quality_check.user` |
| Organizer | `organizer.report.system`、`organizer.report.user` |
| Retriever | `retriever.answer.system`、`retriever.answer.user` |

### 验收标准

- `backend/agents/planner.py` 不再硬编码规划和质检 prompt。
- `backend/agents/organizer.py` 不再硬编码报告生成 prompt。
- `backend/agents/retriever.py` 不再硬编码问答 prompt。
