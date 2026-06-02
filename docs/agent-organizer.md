# Organizer Agent 设计

## 1. 模块职责

### 背景

Searcher 输出的是网页、API 搜索结果和爬取正文的混合资料，内容存在噪声、重复、可信度差异和结构不稳定的问题，不能直接进入报告和知识库。

### 决策

Organizer 负责把 Searcher 输出整理为可阅读、可导航、可切片、可检索的 Markdown 知识报告。Organizer 可以优先使用小模型完成清洗、排序、分块、评分和报告生成；只有在梳理失败、评分不合格或需要分析失败原因时，才升级调用更强的大模型。

### 实现要点

对应代码：

- `backend/agents/organizer.py`
- `backend/services/knowledge_service.py`

核心职责：

- 清洗搜索结果，去除无关噪声。
- 对资料进行可信度排序、去重和整合。
- 生成带 TOC 的 Markdown 报告。
- 对报告进行质量评分。
- 将报告切片写入 `knowledge_chunks`，支持关键词索引和向量索引。
- 生成报告元数据、版本号和执行摘要。
- 将本轮 Organizer 工作记录写入 Redis，供 Planner 和排障流程读取。

非职责：

- 不负责拆解用户任务，该职责属于 Planner。
- 不负责执行搜索和爬虫，该职责属于 Searcher。
- 不负责面向用户做最终问答，该职责属于 Retriever。
- 不允许绕过 contract 直接写 Redis、DB 或调用 Tool。

### 验收标准

- Organizer 输入、输出和存储写入均符合约束接口。
- 报告可以被 `md-editor-v3` 正常渲染。
- 报告可以被切片并写入知识库。
- 失败、低分和超时场景都能向 Planner 返回结构化原因。

## 2. 输入输出

### 背景

Organizer 需要同时服务报告生成、知识入库、后续问答和错误排查，因此输入输出必须保留来源引用、评分、版本和执行过程信息。

### 决策

Organizer 输入来自 Searcher 的搜索结果、Planner 的任务上下文和 Redis 中的工作状态。输出包括 Markdown 报告、TOC、评分、切片、报告摘要、失败原因和 Redis 工作记录。

### 实现要点

输入：

- `task_id`：任务 ID。
- `topic_id`：主题 ID。
- `user_id`：用户 ID，用于版本、报告和知识隔离。
- `topic_title`：主题标题。
- `planner_context`：Planner 输出的章节预期、用户意图和质量要求。
- `search_results`：Searcher 输出的结果列表。
- `quality_feedback`：Planner 质检重试时传入的反馈。

输出：

- `report.content_md`：Markdown 报告正文。
- `report.toc`：目录结构。
- `report.summary`：报告摘要。
- `report.quality_score`：总分。
- `knowledge_chunks`：可检索切片。
- `discarded_items`：低质量或部分可用内容标记。
- `organizer_status`：`completed` / `partial` / `failed`。
- `failure_reason`：失败原因。
- `redis_worklog`：本次整理过程的关键状态。

### 验收标准

- 每条有效内容保留原始 `search_histories.id` 引用集合、发布时间或更新时间、可信度分数。
- 每条低质量内容保留 `discard_reason`。
- 输出失败时必须包含可诊断原因，不允许只返回空结果。

## 3. 工作流程

### 背景

Organizer 的流程需要稳定、可重试、可审计，并且要把清洗、排序、文档生成、评分和入库拆成清晰阶段。

### 决策

Organizer 按“预处理 -> 生成文档 -> 评估 -> 大模型兜底 -> 后处理”的顺序执行。

### 实现要点

1. 预处理（数据处理）

1.1 去除噪声

1.1.1 删除网页结构噪声：

- HTML 标签。
- 脚本。
- 样式。
- 空白字符。
- 乱码。

1.1.2 删除内容噪声：

- 广告。
- 导航栏。
- 版权声明。
- 推荐阅读。
- 过长引用块。
- 重复免责声明。

1.1.3 清洗库建议：

- `readability`
- `trafilatura`
- `boilerpy3`

1.2 排序与去重

1.2.1 内容级去重：

- 对正文计算 SimHash 或 MinHash。
- 相似度 `> 0.85` 视为重复。
- 同组重复内容只保留可信度最高的一条。

1.2.2 可信度排序：

- 官方文档优先。
- GitHub 优先。
- StackOverflow 其次。
- 普通博客最低。

1.2.3 额外加分规则：

| 条件 | 加分 |
|---|---:|
| 更新时间小于 30 天 | +5 |
| 作者认证，例如 GitHub 官方 | +10 |
| 有代码示例 | +5 |
| 被超过 3 个其他来源引用 | +5 |

1.3 内容整合

1.3.1 将相同主题、相同结论或相同技术路径的内容归并到同一组。

1.3.2 同一组内容过多时，以可信度最高的来源作为主材料，其他来源只保留关键差异、补充说明和引用。

1.4 文本分块

1.4.1 按标题和段落切分。

1.4.2 保持语义完整，不截断句子。

1.4.3 每个 chunk 必须保留：

- `source_search_ids`：原始搜索历史 ID 集合。
- `summary`：50-150 字切片摘要。
- 可信度分数。
- 所属章节。
- 在报告中的顺序。

1.4.4 来源 URL、标题、发布时间和摘要不直接重复写入 chunk，通过 `source_search_ids -> search_histories.id -> raw_results` 反查。

1.4.5 支持 overlap，保证上下文连贯。

1.5 标记部分可用内容

1.5.1 低质量内容不直接丢弃，先标记后单独存储。

1.5.2 `discard_reason` 可选值：

- `too_short`
- `low_relevance`
- `duplicate`

1.5.3 低质量内容用于后续错误分析、人工复核或搜索策略修正。

2. 生成文档

2.1 自动生成目录（TOC）。

2.2 生成 Markdown 正文。

2.2.1 正文必须使用 Markdown。

2.2.2 一级标题只用于报告标题。

2.2.3 主体章节使用 `##`，子章节使用 `###`。

2.2.4 每个核心论点尽量附带来源链接。

2.2.5 不输出与主题无关的背景铺垫。

2.2.6 同类内容过多时，以可信度最高的内容作为主叙述，其他内容只截取差异点。

2.3 生成报告版本号。

2.3.1 版本号格式：

```text
{user_id}-{topic_id}-{yyyyMMddHHmmss}-{sequence}
```

2.3.2 `sequence` 使用两位数，例如 `01`、`02`，表示同一用户同一主题下的第几次报告版本。

2.4 对当前文档打分和评估。

2.5 设置超时时间。

2.5.1 单次整理超时时间建议为 3 分钟。

2.5.2 超时视为失败，进入失败分析和重试流程。

2.6 入库 `knowledge_chunks`。

2.6.1 使用双路索引：

- 关键词索引：BM25 或倒排索引。
- 向量索引：Embedding + ANN。

2.6.2 向量模型统一为线上千问 `text-embedding-v4`，维度 `1024`。

3. 评估（梳理成功下）

3.1 评分维度：

| 维度 | 权重 | 标准 |
|---|---:|---|
| 完整性 | 30% | 是否回答主题核心问题 |
| 可信度 | 30% | 内容来源平均可信度分数 |
| 时效性 | 20% | 内容发布时间或更新时间 |
| 相关性 | 20% | 与用户问题或主题的匹配程度 |

3.2 时效性评分：

| 发布时间或更新时间 | 分数 |
|---|---:|
| 小于 7 天 | 100 |
| 小于 30 天 | 80 |
| 小于 1 年 | 50 |
| 大于 1 年 | 20 |

3.3 相关性可以由小模型或关键词计算完成。

3.4 及格线为总分 `>= 60`，不是 `50`，保留质量缓冲。

4. 需要调用大模型的情况判断

4.1 梳理失败时，调用大模型分析失败原因，并按原因重试。

4.2 初步评分不合格时，调用大模型分析是哪一步造成问题，并进行重试。

4.2.1 用户原始描述中的 `scode < 50` 按 `score < 60` 理解，最终阈值以本文件评分规则为准。

4.2.2 大模型需要输出明确的问题位置，例如清洗失败、去重失败、来源质量不足、章节结构错误、相关性不足或时效性不足。

4.3 重试超过 3 次时，向 Planner 报告失败。

4.3.1 失败报告必须包含：

- 最后一次失败原因。
- 已重试次数。
- 失败阶段。
- 是否建议重新搜索。
- 是否建议 Planner 调整任务拆解。

5. 后处理（梳理成功下）

5.1 处理与前版本的关联关系。

5.1.1 比较同一个用户、同一个主题下的前一版报告。

5.1.2 标记知识变更：

- 新增内容。
- 变更内容。
- 废弃内容。

5.2 生成报告记录。

5.2.1 写入 `reports` 表的信息包括：

- 本次搜索内容的简单说明。
- Organizer 自我分析。
- 评分情况。
- 意外说明。
- 下次建议。
- Markdown 正文。
- TOC。
- 摘要。

5.3 汇总记录存入 Redis。

5.3.1 Redis 记录用于 Planner 推进、失败排查和 Agent 工作会话归档。

5.3.2 Redis 中至少保留：

- 当前阶段。
- 已处理来源数量。
- 去重数量。
- 丢弃数量。
- 报告版本号。
- 评分结果。
- 失败或重试记录。

### 验收标准

- Organizer 流程可按阶段定位问题。
- 去重、清洗、评分、入库和报告写入都有可追踪记录。
- 低质量内容不会无痕丢失。
- 报告版本可以按用户和主题追溯。

## 4. Markdown 与 TOC

### 背景

前端阅读页需要目录导航，知识切片也需要章节元数据。

### 决策

Organizer 输出带 YAML front matter 的 Markdown。优先读取 YAML front matter 中的 `toc`；解析失败时扫描 Markdown 标题行生成 fallback TOC。

### 实现要点

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

- front matter 可解析出 `title` 和 `toc`。
- TOC 中每一项能定位到正文标题。
- YAML 解析失败时仍能生成可用目录。

## 5. 报告入库

### 背景

报告生成后需要进入 PostgreSQL 和 pgvector，用于后续列表展示和知识问答。

### 决策

`knowledge_service.store_report()` 负责创建 `Report`、切分 Markdown、生成 embedding、写入 `KnowledgeChunk`。

### 实现要点

写入流程：

1. 创建 `Report`。
2. 按 Markdown 标题切片。
3. 为每个切片生成 50-150 字摘要。
4. 对切片摘要生成 embedding。
5. 批量写入 `knowledge_chunks`。
6. 回填报告状态、结果数、评分和摘要。

切片规则：

- 优先按 `##` / `###` 分段。
- 超过 800 字符时用滑窗切割。
- 滑窗重叠 100 字符。
- 空段落跳过。

每条切片元数据必须包含：

- `source_search_ids`：原始 `search_histories.id` 集合。
- `summary`：切片内容摘要，用于检索预览、快速筛选和向量生成。
- 可信度分数。
- 报告版本号。
- 章节标题。
- 章节层级。
- TOC anchor。

来源 URL、标题、发布时间、摘要等详情由 `search_histories.raw_results` 承担，chunk 只保存引用集合，避免来源信息在多个切片中重复写入。

### 验收标准

- 每个完成报告至少生成一条切片。
- 每条切片包含章节标题、层级、anchor 和父级标题。
- 每条切片包含 `summary`，且 embedding 基于 `summary` 生成，不基于完整 `content` 生成。
- 每条切片通过 `source_search_ids` 关联原始搜索历史。
- `knowledge_chunks` 写入必须满足用户隔离查询链路：`knowledge_chunks -> reports -> search_tasks -> user_id`。
- embedding 维度必须与数据库向量字段一致。

## 6. Prompt 策略

### 背景

Organizer 的提示词属于配置，不应散落在代码里。

### 决策

Organizer prompt 统一存放在 `prompts/organizer.md`，代码通过 `backend/core/prompt_loader.py` 加载。

### 实现要点

- 默认 temperature 使用 `0.4`，保证可读性和稳定结构之间平衡。
- 重试时在 user message 末尾追加质检反馈。
- Prompt 明确要求输出 Markdown、TOC、来源引用和质量分析。
- Prompt 不允许输出与主题无关的铺垫内容。

### 验收标准

- `backend/agents/organizer.py` 不硬编码大段 prompt。
- 修改 Organizer 提示词不需要改 Python 代码。

## 7. 已确认存储与配置

### 背景

Organizer 同时负责内容清洗、可信度排序、文档生成、版本编号、切片入库和版本差异标记。相关策略必须一次讲清楚，避免在多处留下互相冲突的方案。

### 决策

- 向量维度统一为 `1024`，embedding 基于 `knowledge_chunks.summary` 生成。
- 关键词索引使用 PostgreSQL `tsvector`，不引入外部搜索引擎。
- 低质量内容不单独建表，保留在 `search_histories.raw_results`，并写入 `discard_reason`。
- 报告版本号时间戳统一使用 UTC。
- `sequence` 按同一用户、同一主题、当前日期递增，可通过 Redis key 实现。
- 可信度排序规则抽取到 `config/source_credibility.yaml`。
- 前后版本 diff 存入 `knowledge_chunks.content_marked`。

### 实现要点

1. 低质量内容

1.1 Organizer 标记低质量内容时，不把内容移出 `search_histories.raw_results`。

1.2 每条低质量内容必须补充 `discard_reason`，可选值以 `config/source_credibility.yaml` 为准。

2. 报告版本

2.1 版本格式使用：

```text
{user_id}-{topic_id}-{utc_timestamp_to_second}-{sequence}
```

2.2 `sequence` 是当前日期内的递增序号，格式为两位数，例如 `01`、`02`。

2.3 Redis key：

```text
report_version:{user_id}:{topic_id}:{date}:sequence
```

3. 可信度排序

3.1 基础来源分、加分规则、去重阈值和 discard_reason 都进入 `config/source_credibility.yaml`。

3.2 代码不得硬编码官方文档、GitHub、StackOverflow、博客等来源权重。

4. 版本差异

4.1 Organizer 生成新版本时，对比同一用户、同一主题的上一版本 `content` 和本版本 `content`。

4.2 对比结果生成带标记 HTML，写入 `knowledge_chunks.content_marked`。

4.3 前端可以选择渲染原始 `content` 或差异版 `content_marked`。

4.4 标记规则：

| 变更类型 | HTML 标签 | 样式 | 说明 |
|---|---|---|---|
| 删除 | `<del>` | 红色或灰色中划线 | 旧版本有，新版本删除的内容 |
| 新增 | `<ins class="added">` | 蓝色字体 + 浅蓝背景 | 新版本新增内容 |
| 修改 | `<ins class="modified">` | 黄色背景 | 同一位置内容被替换 |

### 验收标准

- Organizer 入库的向量维度、DB schema 和 Tool contract 一致。
- 关键词检索可通过 `knowledge_chunks.search_vector` 执行。
- 低质量内容可从 `raw_results` 追溯，不需要额外表。
- 可信度排序修改只需要改配置文件。
- 前端可基于 `content_marked` 展示新旧版本差异。
