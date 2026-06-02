# 记忆管理子 Agent 设计

## 1. 模块职责

记忆管理子 Agent 负责把任务执行过程中产生的偏好、经验、工作轨迹和记忆淘汰动作落到稳定存储。它不是常驻主 Agent，而是由 Planner 在任务收尾或定时清理场景中生成并调度。

对应存储：

- `zr_user_preferences`
- `zr_skill_memories`
- `zr_semantic_memories`
- `zr_episodic_logs`
- `zr_working_sessions`

## 2. 触发方式

### 背景

Planner 是任务全局状态的 owner，最清楚本次任务是否产生了可沉淀的用户偏好、执行经验和排障记录。直接把这些写入逻辑塞进 Planner 会让 Planner 变成大而全的状态管理器。

### 决策

Planner 只判断是否需要写入或更新记忆；真正的合并、覆盖、计数和持久化由记忆管理子 Agent 完成。

### 实现要点

触发来源：

1. Planner 在任务收尾阶段创建记忆管理子 Agent。
2. Celery Beat 每天夜里 `02:00` 触发记忆淘汰任务。
3. 后续用户主动撤销偏好时，也通过同一子 Agent 执行偏好失效或覆盖。

执行约束：

- 子 Agent 必须通过 `backend/constraint/agent_contracts` 接收任务。
- 子 Agent 写 Redis/DB 前必须通过 `backend/constraint/storage_contracts` 校验。
- 子 Agent 不直接参与搜索、梳理、问答生成。

### 验收标准

- Planner 不直接写入 `zr_user_preferences`、`zr_skill_memories`、`zr_working_sessions` 的业务细节。
- 所有记忆写入都有来源任务、用户、触发原因和审计记录。
- 记忆管理失败不会影响已完成报告的读取，但必须写入工作日志并通知 Planner。

## 3. 记忆写入

### 背景

一次任务可能产生三类可复用信息：用户偏好、Agent 执行经验、Skill 使用反馈。它们的写入规则不同，不能混成一条流水日志。

### 决策

记忆写入按“直接覆盖 / 合并更新 / 分级写入 / 工作归档”四类处理。

### 实现要点

1. 用户偏好写入

1.1 当 Planner 判断本次任务有需要下沉的用户偏好时，子 Agent 写入或更新 `zr_user_preferences`。

1.2 新偏好与旧偏好冲突时，以用户最新明确表达为准。

1.3 隐式偏好必须带 `confidence`，低置信度偏好不得覆盖高置信度显式偏好。

2. Skill 经验分级写入

2.1 当任务完成质量足够优秀，例如 `score >= 95`，子 Agent 总结本次 Agent 执行经验。

2.2 经验按四段式结构写入 `zr_skill_memories`：

- `title`：Skill 名字，用于快速匹配和展示。
- `desc`：Skill 描述，作为第一阶段加载内容，用于判断是否需要加载完整 SOP。
- `content`：可执行 SOP，命中后第二阶段加载。
- `citation`：来源任务、适用边界、失败条件和引用说明，按需第三阶段加载。

2.3 新技能与已有技能近似重叠时，只保留最高质量版本为 `active`，其他版本标记为 `deprecated`。

3. Skill 使用反馈

3.1 本次任务使用了某条 Skill 时，子 Agent 更新：

- `success_count`
- `fail_count`
- `last_used_at`
- `confidence`

3.2 `confidence` 按成功率和人工反馈综合更新，不允许只按调用次数机械增加。

4. Redis 工作区持久化

4.1 任务结束后，子 Agent 将 Redis 中各 Agent 工作细节流程归档到 `zr_working_sessions`。

4.2 归档内容包括 Agent handoff、Tool/MCP 调用摘要、状态变更、错误重试、GuardrailDecision 摘要。

4.3 warning / critical 级护栏审计不写入 `zr_working_sessions`，单独归档到 `log_guardrail`。

### 验收标准

- 用户偏好可被覆盖和撤销。
- Skill 经验不会重复堆积为多个 active 版本。
- Skill 使用反馈能反映成功、失败和最近使用时间。
- Redis 工作区到 `zr_working_sessions` 的归档可用于排查完整任务链路。

## 4. 记忆淘汰

### 背景

长期记忆如果只增不减，会污染检索、拉长 prompt、降低用户体验。不同记忆的淘汰策略不同：用户偏好长期有效，语义和情景记忆需要定期清理，Skill 需要有效性管理。

### 决策

记忆淘汰由 Celery Beat 每天夜里 `02:00` 触发。淘汰动作统一使用逻辑删除或状态变更，不物理删除。

### 实现要点

1. 用户偏好

1.1 `zr_user_preferences` 长期有效。

1.2 新偏好可以覆盖旧偏好，例如“我喜欢简洁”变成“我现在想要详细一点”。

1.3 用户可以主动撤销某个偏好。

2. 语义记忆

2.1 语义记忆表：`zr_semantic_memories`。

2.2 淘汰条件：

```sql
confidence <= 0.6
OR last_accessed < NOW() - INTERVAL '30 days'
```

2.3 命中条件后设置 `deleted_at = NOW()`。

3. 情景记忆

3.1 情景记忆表：`zr_episodic_logs`。

3.2 衰减分数：

```text
score = importance * (1 - days_since_event / half_life)
```

3.3 `half_life` 默认 `7` 天，进入 `config/celery.yaml`。

3.4 PostgreSQL 判断条件：

```sql
importance * (1 - EXTRACT(DAY FROM NOW() - created_at) / 7.0) < 0.1
AND created_at < NOW() - INTERVAL '30 days'
```

3.5 命中条件后设置 `deleted_at = NOW()`。

4. Skill 记忆

4.1 `zr_skill_memories` 长期有效，不主动逻辑删除，只做状态管理。

4.2 状态规则：

| 状态 | 含义 | 触发条件 |
|---|---|---|
| `active` | 当前推荐使用版本 | 默认状态 |
| `deprecated` | 不推荐使用，有更好版本 | 新版本产生后，旧版本标记为 deprecated |
| `archived` | 完全不再使用 | 长期未用或成功率过低 |

4.3 归档条件：

- 成功率 `< 30%` 且使用次数 `> 5`。
- `last_used_at` 超过 `180` 天未使用。

4.4 相同或近似重叠 Skill 中，仅最高质量版本保持 `active`，其他版本标记为 `deprecated`。

### 验收标准

- 淘汰任务每天 `02:00` 可由 Celery Beat 自动触发。
- 淘汰不会物理删除历史数据。
- 语义/情景记忆查询默认过滤 `deleted_at IS NULL`。
- Skill 查询默认只使用 `status = 'active'`。

## 5. 配置项

记忆管理可调参数统一放入 `config/celery.yaml`，不得写死在 Agent 代码里。

核心参数：

- 记忆淘汰任务 cron。
- 情景记忆 half-life。
- 语义记忆置信度阈值。
- 语义记忆最近访问阈值。
- Skill 归档成功率阈值。
- Skill 未使用归档天数。
- 优秀任务写入 Skill 的评分阈值。

## 6. 已确认待实现

1. 完整实现 `zr_user_preferences` 自动更新，由 Planner 生成的记忆管理子 Agent 代理执行。
2. 完整实现 `zr_skill_memories` 分级写入和使用反馈更新，由记忆管理子 Agent 代理执行。
3. 完整实现 Redis 工作区到 `zr_working_sessions` 的持久化，由记忆管理子 Agent 代理执行。
