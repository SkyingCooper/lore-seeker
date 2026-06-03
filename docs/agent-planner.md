# Planner Agent 设计

## 1. 模块职责

Planner 是 Agent 流水线的中枢协调节点，采用 P&E 推理模式：

- **Perception**：收到任务后理解用户意图，将模糊需求转成可执行的结构化计划。
- **Evaluation**：在 Searcher 和 Organizer 完成后判断是否推进下一步，记录失败原因、状态和经验。

Planner 不直接执行搜索和报告生成，但负责决定任务如何拆解、何时交给下游 Agent、失败时如何总结、成功后如何沉淀偏好和经验。

对应代码：

- `backend/agents/planner.py`
- `backend/agents/graph.py`

## 2. 规划阶段

### 背景

用户输入通常由 `title`、`keywords`、`description` 组成，表达的是一个研究意图。直接搜索容易覆盖不足，也无法判断关键词优先级、来源站点和子任务执行顺序。

### 决策

Planner 在流水线入口调用一次大模型，将用户的模糊意图转成机器可执行的结构化计划，写入 Agent state 的 `_plan`，并初始化任务工作区。

### 实现要点

输入：

- 用户输入 `title`
- 关键词 `keywords`
- 描述 `description`
- 任务配置 `topic_config`
- 搜索来源 `source_sites`
- 搜索模式 `search_mode`
- 用户偏好 `preferences`

输出：

```json
{
  "intent_summary": "用户核心意图",
  "focus_areas": ["重点方向"],
  "search_queries": ["优化后的搜索词"],
  "subtasks": [
    {
      "keyword": "子关键词",
      "source_sites": ["https://example.com"],
      "priority": 1,
      "reason": "优先级原因"
    }
  ],
  "expected_chapters": ["预期章节"]
}
```

约束：

- 只有在任务需要拆解时才生成多个子任务。
- 子任务以 `keyword × source_sites` 作为执行单元。
- 每个子任务必须带优先级。
- 输出结构必须能被 Searcher 直接消费。
- 输出必须是可解析 JSON。
- LLM temperature 使用低随机性，保证规划稳定。

详细工作流程：

1. 收到任务后
1.1 从任务对象读取 `title`、`keywords`、`description`。
1.2 理解用户意图，抓住核心研究需求和隐含约束。
1.3 调用一次大模型，将用户的模糊意图转成机器可执行的结构化计划。
1.3.1 判断用户补充信息是否足够，是否需要搜索词优化。
1.3.2 判断任务是否需要拆解。
1.3.3 需要拆解时，将抽象需求拆成多个可执行子任务。
1.3.4 子任务以 `keyword × source_sites` 组织。
1.3.5 为关键词分配优先级，判断哪些关键词更重要。
1.3.6 为高优先级关键词分配更早执行顺序或更多搜索资源。
1.3.7 根据关键词和来源站点特征选择目标来源。
1.3.8 判断每个关键词应该在哪些 `source_sites` 中搜索。
1.3.9 生成标准化子任务列表，供 Searcher 直接执行。
1.3.10 生成 `focus_areas`，作为后续报告梳理重点。
1.3.11 生成 `expected_chapters`，作为 Organizer 的章节结构约束。
1.4 将结构化计划写入 `topic_config["_plan"]`。
1.5 初始化任务工作区，在 Redis 中创建任务上下文。
1.5.1 Redis 工作区记录任务开始时间。
1.5.2 Redis 工作区记录预期子任务数。
1.5.3 Redis 工作区记录当前阶段和 Planner 输出。
1.6 将所有子任务交付给 Searcher。
1.7 更新任务状态为搜索执行中。

Prompt 策略：

- Perception 阶段 temperature 使用 `0.2`。
- Prompt 强制返回 JSON，避免自然语言包裹。
- Prompt 明确引用用户偏好，但不允许偏好覆盖任务主题本身。

### 验收标准

- 单一主题能拆出多个明确搜索方向。
- `search_queries` 可直接交给 Searcher。
- `subtasks` 可被 Searcher 转换为执行队列。
- `expected_chapters` 可作为 Organizer 的结构约束。
- Redis 中存在任务工作区和预期子任务数。

## 3. 搜索结果评估与推进

### 背景

Searcher 执行后可能成功、部分失败或全部失败。Planner 需要判断任务是否可以推进到 Organizer，并把失败原因沉淀下来。

### 决策

Searcher 完成后回到 Planner 做 Evaluation。Planner 根据搜索结果完整度、失败类型和结果相关性决定是否推进下一步。

### 实现要点

详细工作流程：

1. 搜索完成后
1.1 接收 Searcher 返回的执行摘要。
1.2 检查所有子任务是否已结束。
1.3 区分成功、部分失败和全部失败。

2. 搜索失败或部分失败
2.1 汇总失败原因，包括超时、限流、权限、无结果和 provider 错误。
2.2 将失败原因写入 Redis 任务工作区。
2.3 将失败反馈入库，供后续任务调整搜索策略。
2.4 更新任务状态为失败或部分失败。

3. 搜索成功
3.1 检查结果数量和基础相关性。
3.2 搜索结果可用时，通知 Organizer 开始梳理。
3.3 更新任务状态为报告整理中。

### 验收标准

- Searcher 失败后任务状态和失败原因可追踪。
- Searcher 成功后 Planner 能推进到 Organizer。
- Redis 中保留搜索阶段的执行摘要。

## 4. 梳理结果评估与收尾

### 背景

Organizer 生成的 Markdown 需要在入库前检查结构清晰度、信息完整性和重复内容。任务完成后还需要沉淀用户偏好、Agent 经验和运行细节。

### 决策

Planner 模块同时实现 `quality_check` 节点，对 Markdown 报告评分并提供反馈。报告通过后，Planner 负责任务收尾、记忆沉淀和周期性任务创建。

### 实现要点

输入：

- Organizer 输出的 Markdown
- TOC
- 预期章节
- 当前迭代次数

输出：

```json
{
  "score": 82,
  "feedback": "需要补充案例和来源对比",
  "pass": true
}
```

评分维度：

| 维度 | 权重 | 要求 |
|---|---:|---|
| 内容完整性 | 40% | 覆盖预期章节，信息量足够 |
| 结构清晰度 | 30% | 标题层级和 TOC 合理 |
| 信息准确性 | 20% | 无明显矛盾和错误 |
| 可读性 | 10% | 语言流畅，Markdown 规范 |

通过标准：

- `score >= 75`
- 或达到最大重试次数后使用最后一次结果

重试规则：

- 不通过时将 `feedback` 注入 Organizer 下一轮 prompt。
- 最多重试 3 次。
- 每轮反馈累积到 Agent state，避免重复犯同一类错误。

详细工作流程：

1. 梳理完成后
1.1 接收 Organizer 的成功或失败结果。

2. 梳理失败
2.1 汇总失败原因。
2.2 将失败原因写入 Redis。
2.3 将失败原因持久化为反馈记录。
2.4 更新任务状态为失败。

3. 梳理成功
3.1 从 state 读取 Markdown。
3.2 截取报告前 8000 字符作为评分输入，控制 token 成本。
3.3 读取 TOC 和 Planner 生成的 `expected_chapters`。
3.4 检查报告是否覆盖预期章节。
3.5 检查 Markdown 标题层级是否稳定，一级标题是否只用于报告标题。
3.6 检查章节之间是否存在明显重复。
3.7 检查内容是否包含来源、案例、对比或关键论据。
3.8 按内容完整性、结构清晰度、信息准确性、可读性四个维度评分。
3.9 生成可执行的 `feedback`，指出具体章节和修改方向。
3.10 计算 `pass`，默认 `score >= 75` 通过。
3.11 不通过且 `iteration < 3` 时，LangGraph 条件边回到 Organizer。
3.12 不通过但达到最大迭代次数时，接受最后一次报告并结束流程。

4. 任务收尾
4.1 报告通过后，总结本次任务体现出的用户偏好和执行经验。
4.2 Planner 判断是否需要写入或更新记忆。
4.3 如需要写入记忆，Planner 生成记忆管理子 Agent，代理执行 `zr_user_preferences`、`zr_skill_memories` 和 `zr_working_sessions` 的更新。
4.4 如果任务配置包含周期频率，根据当前任务创建下一次周期性任务。
4.5 将 `quality_score`、`quality_feedback` 和 `final` 写入 state。
4.6 更新任务状态为完成。
4.7 统计此次任务消耗的 token 情况，按 `search`、`sort`、`retrieve`、`planner`、`memory_manager`、`context_manager` 等环节汇总，并写入 `reports.token_usage`。

Prompt 策略：

- Evaluation 阶段 temperature 使用 `0.1`。
- 输出必须是 JSON，字段固定为 `score`、`feedback`、`pass`。
- 反馈必须是改写建议，不写泛泛评价。

### 验收标准

- 质量分数写入最终报告。
- 不达标报告触发 Organizer 重试。
- 超过重试次数后流程能结束，不会无限循环。
- 任务完成后用户偏好、经验和工作会话可被追踪。
- 任务完成后 token 消耗按环节写入报告记录。

## 5. 个性化记忆

### 背景

不同用户对报告深度、技术细节、章节数量和来源质量有不同偏好。Planner 是最适合消费偏好的节点。

### 决策

Planner 读取 `zr_user_preferences` 作为计划约束，不再依赖 `users.preferences` JSON 字段。任务完成后的偏好基础写入服务已存在，偏好自动提取和冲突判断由记忆管理子 Agent 接入。

### 实现要点

偏好结构示例：

```json
{
  "preferred_depth": "detailed",
  "preferred_style": "technical",
  "preferred_chapter_count": 5,
  "disliked_sources": ["低质量站点"]
}
```

读取规则：

- `preferred_depth` 影响子查询数量和章节细度。
- `preferred_style` 影响 Planner 给 Organizer 的结构约束。
- `preferred_chapter_count` 影响 `expected_chapters` 数量。
- `disliked_sources` 影响 Searcher 的站点过滤和结果筛选。

### 验收标准

- 有偏好时计划输出能体现用户偏好。
- 无偏好时使用默认规划策略。
- 偏好不会覆盖任务标题和用户本次明确要求。

## 6. State 约定

Planner 读写的关键 state 字段：

| 字段 | 方向 | 说明 |
|---|---|---|
| `query` | 读 | 用户查询 |
| `topic_config` | 读写 | 任务配置，包含 `_plan` |
| `subtasks` | 写 | 标准化子任务列表 |
| `quality_score` | 写 | 最终评分 |
| `quality_feedback` | 写 | 质检反馈 |
| `iteration` | 读写 | 当前重试次数 |
| `final` | 写 | 是否结束流程 |

## 7. 当前状态

- 记忆管理子 Agent 已接入任务收尾流程，当前支持显式偏好、Skill 使用反馈、工作区归档、高分任务 Skill 写入、LLM 隐式偏好抽取、语义记忆提炼和情景日志写入。
- 记忆抽取或写入失败只写入工作日志，不阻断已完成报告。

记忆管理细节见 `agent-memory-manager.md`。
