# 存储层设计

## 1. 模块职责

存储层负责结构化业务数据、报告向量切片、Agent 记忆、会话缓存和异步任务状态。

对应代码：

- `backend/db/models.py`
- `backend/db/schema.sql`
- `backend/core/database.py`
- `backend/core/task_redis.py`

## 2. 存储分层

### 背景

系统既需要关系查询，也需要语义检索和临时任务状态。

### 决策

采用三层存储：

| 层 | 技术 | 职责 |
|---|---|---|
| 关系层 | PostgreSQL | 用户、主题、任务、报告、历史、记忆 |
| 向量层 | pgvector | 报告切片和语义记忆 embedding |
| 缓存/队列层 | Redis | Celery、Session、Token、任务工作区 |

### 实现要点

- 主键统一使用 `BIGSERIAL` / `BigInteger` 自增 ID。
- 业务删除使用 `deleted_at` 逻辑删除。
- PostgreSQL 初始化统一使用 `backend/db/schema.sql`。
- pgvector 维度当前为 `1536`。

### 验收标准

- `models.py` 和 `schema.sql` 字段语义一致。
- 数据可通过 `user_id -> task_id -> report_id` 追溯。
- Redis 临时状态不替代 PostgreSQL 业务主数据。

## 3. 核心业务表

### 背景

任务、报告和知识库需要稳定的关系链路。

### 决策

核心关系为：

```text
User -> Topic -> SearchTask -> Report -> KnowledgeChunk
```

### 实现要点

#### users

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `username` | 注册用户名，游客为空 |
| `email` | 注册邮箱，游客为空 |
| `hashed_password` | bcrypt 哈希 |
| `avatar_url` | 用户头像 |
| `is_guest` | 是否游客 |
| `last_login_at` | 最近登录时间 |

#### topics

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `parent_id` | 父级搜索历史 ID，空值表示整体搜索记录，非空表示子任务搜索记录 |
| `user_id` | 所属用户 |
| `title` | 主题名称 |
| `keywords` | 关键词 JSON |
| `description` | 主题说明 |
| `deleted_at` | 逻辑删除时间 |

#### search_tasks

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `user_id` | 所属用户 |
| `topic_id` | 关联主题 |
| `query` | 快速搜索文本 |
| `source_sites` | 来源站点列表 |
| `search_mode` | `api / crawl / mixed` |
| `frequency` | `once / daily / weekly / biweekly / monthly` |
| `status` | `pending / fetching / organizing / completed / failed` |
| `deleted_at` | 逻辑删除时间 |

#### reports

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `topic_id` | 关联主题 |
| `task_id` | 关联任务 |
| `status` | `completed / partial / failed` |
| `content_md` | Markdown 报告 |
| `toc` | 目录 JSON |
| `summary` | 摘要 |
| `quality_score` | 质量评分 |
| `user_satisfaction` | 用户满意度 |

#### knowledge_chunks

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `report_id` | 所属报告 |
| `chunk_index` | 切片顺序 |
| `section_title` | 章节标题 |
| `section_level` | 章节层级 |
| `section_anchor` | TOC anchor |
| `parent_title` | 父级章节 |
| `content` | 切片正文 |
| `embedding` | `vector(1536)` |
| `metadata` | 扩展元数据 |

#### search_histories

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `user_id` | 所属用户 |
| `task_id` | 关联任务 |
| `topic_id` | 关联主题 |
| `report_id` | 关联报告 |
| `query` | 搜索文本 |
| `raw_results` | 原始搜索结果 |
| `version` | 搜索版本 |

### 验收标准

- 每个报告可回溯任务、主题和用户。
- 每个切片可回溯报告。
- 逻辑删除任务后列表不再展示。

## 4. Agent 记忆表

### 背景

Agent 需要保存任务过程、事件日志、长期语义记忆、用户偏好和可复用技能。

### 决策

Agent 记忆拆成五类表，字段按各自查询模式设计。

### 实现要点

| 表 | 职责 |
|---|---|
| `zr_working_sessions` | 工作记忆归档，活跃态先放 Redis |
| `zr_episodic_logs` | 对话、任务运行、错误等事件流水 |
| `zr_semantic_memories` | 长期语义记忆，summary embedding |
| `zr_user_preferences` | 显式/隐式用户偏好 |
| `zr_skill_memories` | SOP 技能库和触发词 |

当前状态：

- 表结构已建模。
- 完整写入服务已确认待实现。

### 验收标准

- 用户偏好通过 `zr_user_preferences` 存储。
- Agent 运行记录可关联 `task_id`。
- 语义记忆可通过 pgvector 检索。

## 5. Redis Key

### 背景

Redis 既承载 Celery，也承载 Session、Token 和任务工作区。

### 决策

Redis 只保存临时状态，长期业务数据最终落 PostgreSQL。

### 实现要点

| 用途 | Key 模式 | TTL |
|---|---|---|
| Celery 结果 | `celery-task-meta-*` | Celery 管理 |
| 游客 Session | `session:{id}` | 7 天并刷新 |
| Refresh Token | `refresh_token:{user_id}` | 7 天 |
| Token 黑名单 | `jwt:blacklist:{jti}` | access token 剩余寿命 |
| 任务上下文 | `task:{task_id}:context` | 一次性任务 1 小时，周期任务 30 天 |
| 子任务状态 | `task:{task_id}:subtasks` | 同任务上下文 |
| 原始结果 | `task:{task_id}:results_raw` | 同任务上下文 |
| 精炼结果 | `task:{task_id}:results_refined` | 同任务上下文 |
| 工作日志 | `task:{task_id}:working_log` | 同任务上下文 |

### 验收标准

- 一次性任务完成后 Redis 工作区会过期。
- 周期性任务保留更长状态窗口。
- Redis key 不保存不可恢复的唯一业务数据。

## 6. 向量索引

### 背景

数据量增长后，向量全表扫描会影响检索性能。

### 决策

pgvector 使用 HNSW 索引作为增长后的优化手段。

### 实现要点

```sql
CREATE INDEX idx_knowledge_chunks_embedding
ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_zr_semantic_memories_embedding
ON zr_semantic_memories USING hnsw (embedding vector_cosine_ops);
```

### 验收标准

- 小数据量可以不启用 HNSW。
- 大数据量启用后检索延迟下降。
- 索引字段与 embedding 维度一致。
