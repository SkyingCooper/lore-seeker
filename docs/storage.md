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
- pgvector 维度统一为 `1024`。

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
| `token_usage` | 此次任务消耗的 token 数量，按环节细分 |
| `quality_score` | 质量评分 |
| `user_satisfaction` | 用户满意度 |

`reports.token_usage` 结构：

```json
{
  "total": 15234,
  "breakdown": {
    "search": {
      "input_tokens": 0,
      "output_tokens": 0,
      "total": 0
    },
    "sort": {
      "input_tokens": 2340,
      "output_tokens": 512,
      "total": 2852
    },
    "retrieve": {
      "input_tokens": 5890,
      "output_tokens": 1024,
      "total": 6914
    },
    "planner": {
      "input_tokens": 3200,
      "output_tokens": 1568,
      "total": 4768
    },
    "memory_manager": {
      "input_tokens": 0,
      "output_tokens": 0,
      "total": 0
    },
    "context_manager": {
      "input_tokens": 0,
      "output_tokens": 0,
      "total": 0
    }
  },
  "model_used": {
    "search": null,
    "sort": "qwen-turbo",
    "retrieve": "qwen-turbo",
    "planner": "qwen-plus"
  },
  "timestamp": "2026-06-02T14:30:00Z"
}
```

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
| `content_marked` | 与前版本对比后的带标记 HTML，用于前端对比渲染 |
| `summary` | 切片内容摘要（50-150 字），用于检索预览和快速筛选 |
| `source_search_ids` | 原始搜索历史 ID 集合，通过 `search_histories.id` 反查来源 |
| `embedding` | `summary` 的向量，`vector(1024)` |
| `metadata` | 扩展元数据，不重复保存来源 URL / 标题 |
| `search_vector` | PostgreSQL `tsvector` 关键词检索列 |

#### search_histories

| 字段 | 说明 |
|---|---|
| `id` | 自增主键 |
| `parent_id` | 父级搜索历史；`NULL` 表示整体搜索记录，非空表示子任务级记录 |
| `user_id` | 所属用户 |
| `task_id` | 关联任务 |
| `topic_id` | 关联主题 |
| `report_id` | 关联报告 |
| `query` | 搜索文本 |
| `source_sites` | 本次实际执行的搜索来源集合 |
| `search_mode` | 本次实际执行的搜索方式：`api / crawl / mixed` |
| `status` | 本次搜索执行状态：`completed / partial / failed` |
| `result_count` | 本次搜索返回的有效结果数量 |
| `retry_count` | 本次搜索重试次数 |
| `execution_duration` | 本次搜索耗时（秒） |
| `failure_reason` | 本次搜索失败或部分失败原因 |
| `raw_results` | 原始搜索结果，保留来源、标题、URL、发布时间、摘要等详情 |
| `metadata` | 搜索策略、限流退避、扩展关键词、质量摘要等扩展元数据 |
| `version` | 搜索版本 |

`search_histories` 是来源事实表，记录 Searcher 本次实际搜索了哪些来源、用了什么方式、结果如何。`knowledge_chunks` 不再重复保存 URL、标题等来源详情，只保存 `source_search_ids`，通过搜索历史反查原始来源。

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
| `log_guardrail` | Pydantic AI 护栏 warning / critical 审计 |

当前状态：

- 表结构已建模。
- 完整写入服务已确认待实现。

记忆淘汰字段：

| 表 | 字段 | 说明 |
|---|---|---|
| `zr_semantic_memories` | `confidence` | 语义记忆置信度，范围 `0~1`，用于排序和淘汰 |
| `zr_semantic_memories` | `last_accessed` | 最近使用时间，用于淘汰 |
| `zr_semantic_memories` | `deleted_at` | 逻辑删除时间 |
| `zr_episodic_logs` | `importance` | 情景记忆重要性，范围 `0~1`，用于淘汰 |
| `zr_episodic_logs` | `deleted_at` | 逻辑删除时间 |
| `zr_skill_memories` | `success_count` | 成功使用次数 |
| `zr_skill_memories` | `fail_count` | 失败次数 |
| `zr_skill_memories` | `last_used_at` | 最近使用时间 |
| `zr_skill_memories` | `status` | `active / deprecated / archived` |
| `zr_skill_memories` | `confidence` | Skill 置信度，默认 `0.5`，可按成功次数 / 总次数计算 |

Skill 记忆加载字段：

| 字段 | 说明 |
|---|---|
| `title` | Skill 名字 |
| `desc` | Skill 描述，第一阶段加载 |
| `content` | 完整 SOP，第二阶段命中后加载 |
| `citation` | 来源、边界和解释，第三阶段按需加载 |

### 验收标准

- 用户偏好通过 `zr_user_preferences` 存储。
- Agent 运行记录可关联 `task_id`。
- 语义记忆可通过 pgvector 检索。
- 有淘汰策略的记忆查询必须过滤 `deleted_at IS NULL`。

## 5. Redis Key

### 背景

Redis 既承载 Celery，也承载 Session、Token、任务工作区、Retriever 会话缓存、语义记忆缓存和 LLM 缓存。

### 决策

Redis 只保存临时状态，长期业务数据最终落 PostgreSQL。Redis key、缓存内容、owner、TTL 和过期策略集中定义在 `redis.md`。

### 实现要点

| 用途 | Key 模式 | TTL |
|---|---|---|
| Celery 结果 | `celery-task-meta-*` | Celery 管理 |
| 游客 Session | `session:{id}` | 7 天并刷新 |
| Refresh Token | `refresh_token:{user_id}` | 7 天 |
| Access Token 黑名单 | `bl_access:{jti}` | access token 剩余寿命 |
| 滑块验证码 | `captcha:{token}` | `CAPTCHA_TTL`，验证成功删除 |
| 任务上下文 | `task:{task_id}:context` | 一次性任务 1 小时，周期任务 30 天 |
| 子任务状态 | `task:{task_id}:subtasks` | 同任务上下文 |
| 原始结果 | `task:{task_id}:results_raw` | 同任务上下文 |
| 精炼结果 | `task:{task_id}:results_refined` | 同任务上下文 |
| 工作日志 | `task:{task_id}:working_log` | 同任务上下文 |
| Retriever 会话上下文 | `session:{user_id}:{session_id}:context` | 30 分钟 |
| Retriever 语义记忆 | `user:{user_id}:semantic` | 30 分钟 |
| Retriever 工作日志 | `session:{user_id}:{session_id}:retriever_worklog` | 30 分钟 |
| LLM 响应缓存 | `llm:cache:{model}:{prompt_hash}` | 7 天 |

### 验收标准

- 一次性任务完成后 Redis 工作区会过期。
- 周期性任务保留更长状态窗口。
- Redis key 不保存不可恢复的唯一业务数据。
- Redis 详细规范以 `redis.md` 为准。

## 6. 向量索引

### 背景

向量检索是系统核心能力，不能依赖全表扫描作为长期方案。

### 决策

所有涉及向量检索的索引统一使用 HNSW。不得使用未声明的向量索引类型，也不得把 HNSW 作为“后续可选项”长期搁置。

### 实现要点

```sql
CREATE INDEX idx_knowledge_chunks_embedding
ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_zr_semantic_memories_embedding
ON zr_semantic_memories USING hnsw (embedding vector_cosine_ops);
```

### 验收标准

- 所有 `vector` 字段对应的检索索引都使用 HNSW。
- 索引字段与 embedding 维度一致。
