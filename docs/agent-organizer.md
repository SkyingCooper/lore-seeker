# Organizer Agent 设计

## 1. 模块职责

Organizer 将 Searcher 输出的原始资料整理为结构化 Markdown 报告，并生成 TOC、摘要和可入库的章节结构。

对应代码：

- `backend/agents/organizer.py`
- `backend/services/knowledge_service.py`

## 2. Markdown 报告生成

### 背景

搜索结果是碎片化资料，不能直接作为知识库内容。系统需要生成可阅读、可导航、可切片入库的报告。

### 决策

Organizer 输出带 YAML front matter 的 Markdown。TOC 和正文由同一次 LLM 调用生成，保证目录和内容一致。

### 实现要点

输入：

- 原始搜索结果，最多取前 20 条。
- Planner 的 `expected_chapters`。
- 质检反馈 `quality_feedback`。

输出示例：

```markdown
---
title: 文档标题
toc:
  - level: 2
    title: 章节标题
    anchor: section-anchor
---

# 文档标题

## 章节标题
正文...
```

生成约束：

- 正文必须使用 Markdown。
- 一级标题只用于报告标题。
- 主体章节使用 `##`，子章节使用 `###`。
- 每个核心论点尽量附带来源链接。
- 质检重试时必须针对 feedback 修改。

详细工作流程：

1. 从 state 读取 Searcher 输出的结果列表。
2. 丢弃正文过短、标题缺失或 URL 异常的低质量结果。
3. 限制最多输入前 20 条结果，控制 LLM token 成本。
4. 读取 Planner 的 `expected_chapters` 作为章节结构约束。
5. 读取 `quality_feedback`，在重试轮次中注入改写要求。
6. 将搜索结果整理成编号资料块，保留标题、URL 和摘要。
7. 让 LLM 生成带 YAML front matter 的 Markdown。
8. front matter 中必须包含 `title` 和 `toc`。
9. 正文使用 `#` 作为报告标题，`##` / `###` 作为正文层级。
10. 对关键结论补充来源链接，避免无出处断言。
11. 解析 LLM 输出，拆分 front matter 和正文。
12. 将 Markdown、TOC、摘要候选和质量上下文写回 state。

Prompt 策略：

- temperature 使用 `0.4`，保证可读性和稳定结构之间平衡。
- 重试时在 user message 末尾追加 `质检反馈（请改进）：{feedback}`。
- Prompt 明确要求不输出与主题无关的背景铺垫。

### 验收标准

- Markdown 可被 `md-editor-v3` 正常渲染。
- front matter 可解析出 `title` 和 `toc`。
- 报告结构能直接用于切片和目录导航。

## 3. TOC 解析

### 背景

前端阅读页需要目录导航，知识切片也需要章节元数据。

### 决策

优先读取 YAML front matter 中的 `toc`；解析失败时扫描 Markdown 标题行生成 fallback TOC。

### 实现要点

TOC 数据结构：

```python
[
  {"level": 2, "title": "章节标题", "anchor": "section-anchor"},
  {"level": 3, "title": "小节标题", "anchor": "sub-section-anchor"}
]
```

anchor 规则：

- 去除特殊符号。
- 空格转 `-`。
- 英文转小写。
- 保留中文字符。

### 验收标准

- TOC 中每一项能定位到正文标题。
- YAML 解析失败时仍能生成可用目录。

## 4. 报告入库

### 背景

报告生成后需要进入 PostgreSQL 和 pgvector，用于后续列表展示和知识问答。

### 决策

`knowledge_service.store_report()` 负责创建 `Report`、切分 Markdown、生成 embedding、写入 `KnowledgeChunk`。

### 实现要点

写入流程：

1. 创建 `Report`。
2. 按 Markdown 标题切片。
3. 对切片文本生成 embedding。
4. 批量写入 `knowledge_chunks`。
5. 回填报告状态、结果数、评分和摘要。

切片规则：

- 优先按 `##` / `###` 分段。
- 超过 800 字符时用滑窗切割。
- 滑窗重叠 100 字符。
- 空段落跳过。

### 验收标准

- 每个完成报告至少生成一条切片。
- 每条切片包含章节标题、层级、anchor 和父级标题。
- embedding 维度与数据库 `vector(1536)` 一致。

## 5. 相关文件

- `backend/agents/organizer.py`：Organizer 节点实现，包含 Markdown 生成和 TOC 提取。
- `backend/services/knowledge_service.py`：报告写入、Markdown 切片和向量入库。
- `backend/db/models.py`：`Report` 和 `KnowledgeChunk` 模型。

## 6. 已确认待实现

- 报告摘要和搜索历史回填需要在 worker 成功路径中保持一致。
