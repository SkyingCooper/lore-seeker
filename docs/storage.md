# 存储层设计

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│  第一层：关系层（PostgreSQL）                                  │
│  存储结构化元数据，支持复杂查询和关联                            │
├─────────────────────────────────────────────────────────────┤
│  第二层：向量层（pgvector 扩展）                               │
│  知识切片 + 语义记忆的向量表示，支持语义相似度检索               │
├─────────────────────────────────────────────────────────────┤
│  第三层：缓存/队列层（Redis）                                  │
│  Celery 任务队列 + 工作记忆活跃状态                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 业务数据表

### User

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| email | String(255) | 注册用户邮箱，可为空（游客） |
| hashed_password | String(255) | bcrypt 哈希，可为空 |
| fingerprint | String(255) | 浏览器指纹，游客身份标识 |
| is_guest | Boolean | 是否游客 |
| created_at | DateTime | 创建时间 |

### Topic

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User |
| name | String(255) | 主题名称 |
| description | Text | 主题描述 |
| target_sites | JSON | 指定搜索网站列表 |
| search_mode | String(20) | api / crawl |

### SearchTask

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User |
| topic_id | UUID | 外键 → Topic（可为空） |
| query | Text | 用户原始查询 |
| status | String(20) | pending / running / done / failed |
| quality_score | Float | 质检最终得分 |
| created_at | DateTime | 创建时间 |
| finished_at | DateTime | 完成时间 |

### Report

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| task_id | UUID | 外键 → SearchTask（唯一） |
| title | String(500) | 报告标题 |
| content_md | Text | 完整 Markdown 正文 |
| toc | JSON | 目录结构 `[{level, title, anchor}]` |
| summary | Text | 摘要（可为空） |
| created_at | DateTime | 创建时间 |

### KnowledgeChunk（向量层 - 报告切片）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| report_id | UUID | 外键 → Report |
| chunk_index | Integer | 切片序号 |
| content | Text | 切片文本 |
| embedding | Vector(1536) | 向量表示 |
| metadata | JSON | 扩展元数据 |

### SearchHistory

每次搜索产生一条，作为用户历史列表的入口，关联知识库版本和 Agent 工作记忆。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User |
| task_id | UUID | 外键 → SearchTask（唯一） |
| topic_id | UUID | 外键 → Topic（冗余，加速按主题过滤） |
| query | Text | 原始查询（冗余，列表页免 JOIN） |
| version | Integer | 同 topic / query 下第 n 次搜索，由 service 层写入时计算 |
| report_title | String(500) | 报告标题（任务完成后回填） |
| report_summary | Text | 报告摘要（任务完成后回填，快速预览） |
| created_at | DateTime | 创建时间 |

**关联查询路径**：
```
SearchHistory.task_id
  → SearchTask → Report          # 查看本次搜索产生的知识库内容
  → SearchTask.working_sessions  # 查看本次搜索的所有 Agent 工作记忆
```

`report_title` / `report_summary` 由 Celery worker 在任务完成（status=done）后异步回填，列表页直接读取无需跨表 JOIN。

`version` 字段由 service 层在写入时计算：同一 `(user_id, topic_id)` 下已有记录数 + 1；无 topic 时按 `(user_id, query)` 分组。

---

## Agent 五类记忆层

Agent 的记忆体系独立于业务数据，分为五类，各司其职：

```
┌──────────────┬──────────────────────────────────────────────────────────┐
│  记忆类型    │  职责                         存储位置                    │
├──────────────┼──────────────────────────────────────────────────────────┤
│  工作记忆    │  当前目标、执行步骤、工具缓存  Redis（活跃）→ PG（归档）  │
│  情景记忆    │  流水账日记，记录"发生了什么"  PostgreSQL                  │
│  语义记忆    │  知识规律 + 向量检索           PostgreSQL + pgvector        │
│  用户偏好    │  显式/隐式配置 key-value       PostgreSQL                  │
│  Skill 记忆  │  操作 SOP，三层按需加载        PostgreSQL                  │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### 工作记忆（working_sessions）

活跃状态存于 Redis（`working_session:{session_key}`），会话结束后异步归档到此表，Redis 中删除。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User |
| task_id | UUID | 外键 → SearchTask（可为空，关联触发本次工作记忆的搜索） |
| session_key | String(255) | Redis key，唯一 |
| goal | Text | 当前目标 |
| current_step | Integer | 执行到第几步 |
| steps | JSON | 步骤执行记录列表 |
| tool_cache | JSON | 工具调用结果缓存 |
| status | String(20) | active / archived |
| started_at | DateTime | 会话开始时间 |
| ended_at | DateTime | 会话结束时间（可为空） |

**生命周期**：
```
会话开始 → 写入 Redis（status=active）
         → 会话结束：异步 upsert 到 working_sessions（status=archived），删除 Redis key
```

### 情景记忆（episodic_logs）

系统的"流水账日记"，记录每次完整的对话记录、任务执行日志等事件。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User |
| task_id | UUID | 外键 → SearchTask（可为空） |
| session_key | String(255) | 关联工作记忆 session_key（可为空） |
| event_type | String(50) | conversation / task_run / search / error |
| content | Text | 完整对话记录或任务执行日志 |
| metadata | JSON | 扩展上下文（token 数、耗时等） |
| created_at | DateTime | 记录时间 |

### 语义记忆（semantic_memories）

从对话和任务中提炼的知识/规律，**embedding 基于 summary 计算**，保持向量维度轻量。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User（null = 全局记忆） |
| title | String(500) | 一句话概括，用于快速索引 |
| summary | Text | 精简摘要，用于快速预览和向量化 |
| content | Text | 完整内容 |
| embedding | Vector(1536) | summary 的向量 |
| source_type | String(50) | 来源类型：report / conversation / manual |
| source_id | UUID | 来源记录 ID（可为空） |
| created_at | DateTime | 创建时间 |

**检索方式**：向量相似度检索 summary embedding → 命中后按需加载 content。

### 用户偏好（user_preferences）

用户的显式/隐式配置，key-value 形式，独立成表替代 User.preferences JSON 字段。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| user_id | UUID | 外键 → User |
| key | String(255) | 偏好键，如 `search_depth`、`output_lang` |
| value | JSON | 偏好值（任意类型） |
| category | String(20) | explicit（用户主动设置）/ implicit（Agent 推断） |
| confidence | Float | 隐式偏好的置信度（0~1），可为空 |
| updated_at | DateTime | 最后更新时间 |
| created_at | DateTime | 创建时间 |

### Skill 记忆（skill_memories）

操作 SOP 库，三层结构设计，按不同需要按需加载（类似 Claude memory 的分层索引）：

| 层级 | 字段 | 说明 | 加载时机 |
|---|---|---|---|
| 一级 | title | 关键词/标题 | 匹配索引时加载 |
| 二级 | content | 完整 SOP 步骤内容 | 命中后加载 |
| 三级 | citation | 引用与解释（来源、边界、例外） | 需要溯源时加载 |

完整字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | UUID | 主键 |
| title | String(255) | 一级：关键词/标题 |
| content | Text | 二级：完整 SOP 内容 |
| citation | Text | 三级：引用与解释（可为空） |
| scope | String(20) | global（系统内置）/ user（用户私有） |
| user_id | UUID | 外键 → User（scope=user 时有值） |
| trigger_patterns | JSON | 触发匹配关键词列表 |
| usage_count | Integer | 使用次数 |
| last_used_at | DateTime | 最后使用时间 |
| created_at / updated_at | DateTime | 创建/更新时间 |

---

## 向量索引

语义记忆和知识切片均使用 pgvector，索引建议：

```sql
-- semantic_memories：summary embedding
CREATE INDEX ON semantic_memories USING hnsw (embedding vector_cosine_ops);

-- knowledge_chunks：报告切片
CREATE INDEX ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
```

当前未在 `init.sql` 中创建索引（数据量小时全表扫描足够），待数据量增长后添加。

## Redis 使用

| 用途 | Key 模式 | TTL |
|---|---|---|
| Celery 任务队列 | `celery-task-meta-{task_id}` | 由 Celery 管理 |
| 工作记忆活跃态 | `working_session:{session_key}` | 会话结束时主动删除 |

## 相关文件

- `backend/db/models.py` — SQLAlchemy 模型定义（含五类记忆表）
- `backend/db/init.sql` — PostgreSQL 初始化（启用 vector 扩展）
- `backend/core/database.py` — 异步引擎 + Session 工厂

---

## 设计决策记录

### 2026-05-27 — 五类记忆层重设计

**背景**：原设计仅有 `User.preferences` JSON 字段记录偏好，缺乏对 Agent 记忆的系统性建模，无法支持复杂的跨会话上下文恢复和知识积累。

**决策**：将 Agent 记忆显式拆分为五类，各自独立成表：
- 工作记忆用 Redis 做热存储，归档后落库，避免 DB 写放大
- 情景记忆独立成表，保留完整"发生了什么"的时序日志
- 语义记忆 embedding 只对 summary 做向量化（而非 content），降低向量存储成本，检索命中后再按需加载全文
- 用户偏好从 User.preferences JSON 字段中独立成 user_preferences 表，支持置信度追踪和 explicit/implicit 区分
- Skill 记忆的三层结构（title/content/citation）模仿 Claude memory 的分层索引，按需加载，避免每次检索都加载完整 SOP

**放弃的方案**：
- 统一用一张 memory 表加 type 字段区分：无法为每类记忆设计专属字段（如 skill 的 trigger_patterns、working session 的 steps）
- 语义记忆对 content 做向量化：content 通常较长，embedding 质量反而低于 summary，且存储成本高

**影响范围**：`db/models.py`、`db/init.sql`（需 enable vector）、后续 memory service
