# 规划 Agent (Planner)

## 职责

规划 Agent 是整个流水线的"大脑"，承担两个阶段的工作：
1. **Perception**：在流水线入口，理解用户意图，生成搜索计划
2. **Evaluation**：在流水线出口，对整理结果质检评分，驱动重试或结束

## P&E 推理设计

### Perception 阶段

**输入**：用户原始查询 + 主题配置（目标网站、搜索模式、历史偏好）

**输出**（JSON）：
```json
{
  "search_queries": ["子查询1", "子查询2", "..."],
  "focus_areas": ["重点方向1", "..."],
  "expected_chapters": ["章节标题1", "..."]
}
```

**推理逻辑**：
- 识别查询中的模糊表达，补全语义（如"Python 异步"→ 补全为"Python asyncio 原理与实践"）
- 将单一查询拆解为 3-5 个子查询，覆盖主题的不同维度（概念、原理、实践、对比、案例）
- 预判知识体系结构，生成预期章节列表，作为 Organizer 的方向约束
- 读取用户 `preferences` 字段，调整搜索深度和内容风格偏好

**Prompt 策略**：temperature=0.2，低随机性保证计划稳定性

### Evaluation 阶段

**输入**：整理 Agent 输出的 Markdown 文档（截取前 8000 字符）

**输出**（JSON）：
```json
{
  "score": 82,
  "feedback": "第三章缺少代码示例，建议补充；第一章与第二章内容有重叠",
  "pass": true
}
```

**评分维度**：
| 维度 | 权重 | 说明 |
|---|---|---|
| 内容完整性 | 40% | 是否覆盖了预期章节，信息是否充分 |
| 结构清晰度 | 30% | 层级是否合理，TOC 是否准确 |
| 信息准确性 | 20% | 是否存在明显错误或矛盾 |
| 可读性 | 10% | 语言是否流畅，格式是否规范 |

**通过标准**：score ≥ 75

**重试机制**：
- 不通过时，将 `feedback` 注入 Organizer 的下一轮 prompt
- 最多重试 3 次（`iteration` 计数器控制），超过后强制结束，取最后一次结果
- 每次重试的 feedback 会叠加，避免 Organizer 遗忘前几轮的改进要求

**Prompt 策略**：temperature=0.1，极低随机性保证评分一致性

## 个性化记忆

规划 Agent 通过 `User.preferences` 字段积累用户偏好：

```json
{
  "preferred_depth": "detailed",
  "preferred_style": "technical",
  "preferred_chapter_count": 5,
  "disliked_sources": ["某低质量网站"]
}
```

**写入时机**：每次任务完成后，根据用户的后续修改行为（如删除某章节、重新搜索）更新偏好（待实现）

## 相关文件

- `backend/agents/planner.py` — 实现
- `backend/agents/graph.py` — `planner_node`、`quality_check_node`、`should_retry` 节点注册

---

## 2025-05-27 — 初始设计

**背景**：需要一个能拆解任务、质检输出的中枢 Agent。

**决策**：将 Planner 拆成两个 LangGraph 节点（`planner` 和 `quality_check`），共用同一个模块文件，通过 `should_retry` 条件边控制循环。

**放弃的方案**：
- 单节点同时做规划和质检：职责混乱，prompt 过长，效果差
- 独立质检 Agent：增加一个 LLM 调用，成本更高，且质检逻辑与规划强相关

**影响范围**：`agents/planner.py`、`agents/graph.py`
