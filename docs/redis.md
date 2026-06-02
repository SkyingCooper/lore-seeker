# Redis 缓存设计

## 1. 设计原则

### 背景

Redis 在系统中同时承载认证状态、验证码、Celery、任务执行工作区、Agent 会话上下文、语义记忆缓存和 LLM 缓存。如果 key 和 TTL 分散定义，容易出现状态丢失、缓存长期占用、敏感信息进入日志或 Agent 绕过约束直接读写 Redis。

### 决策

Redis 只保存临时状态，不作为长期业务事实来源。所有 Redis key 必须先在 `backend/constraint/storage_contracts/redis/key_patterns.yaml` 中声明，value 结构必须在 `backend/constraint/storage_contracts/redis/data_schema.json` 中定义。

### 实现要点

- PostgreSQL 是长期事实来源。
- Redis key 必须带清晰命名空间。
- Auth、任务工作区、Retriever 会话缓存、语义记忆缓存、LLM 缓存互相隔离。
- 含 PII 或认证状态的 key 不允许写入普通日志。
- Agent 工作日志最终归档到 `zr_working_sessions`。
- 任务工作区写入必须通过 `backend/constraint/storage_contracts/redis/data_schema.json` 校验。

### 验收标准

- 新增 Redis key 前必须先补 contract 和本文档。
- Redis 中不存在不可恢复的唯一业务数据。
- 过期策略必须和业务生命周期一致。

## 2. Auth 缓存

### 背景

认证模块需要支持游客 Session、注册用户 Refresh Token、Access Token 登出失效和验证码校验。

### 决策

Access Token 本身不常驻 Redis，只在登出后写入黑名单。Refresh Token 存储在 Redis 中用于刷新校验和轮换。游客态使用 Session Cookie 关联 Redis Session。

### 实现要点

| 用途 | Key | Owner | 内容 | TTL | 过期设计 |
|---|---|---|---|---|---|
| 游客 Session | `session:{session_id}` | `api/auth` | `user_id`、`is_guest`、浏览器指纹、创建时间、最近访问时间 | 7 天 | 每次读取刷新 7 天 |
| Refresh Token | `refresh_token:{user_id}` | `api/auth` | 当前有效 refresh token 原值 | 与 refresh token 有效期一致，当前为 7 天 | 登录/注册/刷新时轮换覆盖 |
| Access Token 黑名单 | `bl_access:{jti}` | `api/auth` | 登出或撤销的 access token `jti` 标记 | access token 剩余寿命 | TTL 到期自动失效 |
| 滑块验证码 | `captcha:{token}` | `api/captcha` | 验证码挑战标记 | 300 秒 | 验证成功立即删除 |

### 验收标准

- Refresh Token 不允许长期无 TTL 保存。
- Access Token 黑名单 TTL 必须等于 token 剩余寿命。
- 验证码 token 只能一次性使用。

## 3. 任务工作区

### 背景

一次完整搜索任务会经过 Planner、Searcher、Organizer、Retriever，以及 MCP / Tool 调用。任务执行中需要保存 Agent 交互、Tool 交互、中间结果、状态和完成情况。

### 决策

一次完整任务使用 `task:{task_id}:*` 作为 Redis 工作区。一次性任务 TTL 为 1 小时；周期任务 TTL 为 30 天。任务结束后工作日志归档到 `zr_working_sessions`。

### 实现要点

| 用途 | Key | Owner | 内容 | TTL | 过期设计 |
|---|---|---|---|---|---|
| 任务上下文 | `task:{task_id}:context` | `planner` | 任务状态、当前 Agent、开始时间、预期子任务数、Planner 输出、失败原因 | 一次性 1 小时；周期任务 30 天 | 随任务频率设置 |
| 子任务状态 | `task:{task_id}:subtasks` | `searcher` | 子任务总数、完成数、失败数、子任务列表和状态 | 同任务上下文 | 随任务上下文过期 |
| 原始搜索结果 | `task:{task_id}:results_raw` | `searcher` | 搜索 API / 爬虫返回的标准化原始结果 | 同任务上下文 | Organizer 读取后仍保留到 TTL |
| 精炼结果 | `task:{task_id}:results_refined` | `organizer` | 清洗、去重、初步整理后的结果 | 同任务上下文 | 报告入库后仍保留到 TTL |
| 工作日志 | `task:{task_id}:working_log` | `planner` | 各 Agent 工作状态、Tool/MCP 调用摘要、异常、完成状态 | 同任务上下文 | 会话结束归档到 `zr_working_sessions` |
| 报告版本序列 | `report_version:{user_id}:{topic_id}:{date}:sequence` | `organizer` | 当前日期内同一用户同一主题的报告版本递增序列 | 2 天 | 用于生成 `...-01 / ...-02`，过期后自然清理 |

工作日志至少记录：

- Agent 名称。
- 当前步骤。
- 与其他 Agent 的交互摘要。
- Tool / MCP 调用摘要。
- 输入输出 contract 校验结果。
- `GuardrailDecision` 摘要，包括 hook、allowed、alert_level、reason、operation、tool_name。
- 当前状态和完成状态。
- 错误与重试信息。

### 验收标准

- 所有 Agent 只能写自己被允许的 `task:{task_id}:*` key。
- `working_log` 必须能还原任务执行链路。
- 任务工作区不保存数据库唯一主数据。
- `backend/core/task_redis.py` 写入 `context`、`subtasks`、`results_raw`、`results_refined`、`working_log` 前必须调用 `validate_redis_value()`。

## 4. Retriever 会话缓存

### 背景

问答 Agent 每轮对话前需要读取当前会话最近上下文、情景记忆和语义记忆。直接每轮查库会造成重复开销，也会丢失当前会话中尚未归档的短期信息。

### 决策

Retriever 首轮对话从数据库预热情景记忆和语义记忆到 Redis；后续轮次优先从 Redis 读取。情景记忆和语义记忆在 Redis 中保留 30 分钟。会话空闲 5 分钟后，情景记忆和语义记忆按规则落库。

### 实现要点

| 用途 | Key | Owner | 内容 | TTL | 过期设计 |
|---|---|---|---|---|---|
| 会话上下文 / 情景记忆 | `session:{user_id}:{session_id}:context` | `retriever` | 当前会话最近 5 轮对话，以及首轮从 `zr_episodic_logs` 预热的最近 5 条情景记忆 | 30 分钟 | 每轮对话刷新；空闲 5 分钟后可归档 |
| 用户语义记忆缓存 | `user:{user_id}:semantic` | `retriever` | 首轮从 `zr_semantic_memories` 加载的语义记忆 | 30 分钟 | 每轮对话刷新；空闲 5 分钟后可归档 |
| Retriever 工作日志 | `session:{user_id}:{session_id}:retriever_worklog` | `retriever` | 本会话意图识别、BM25/向量召回数量、RRF 候选数、Rerank 分数、大模型触发原因、记忆写入状态 | 30 分钟 | 会话结束后归档或随 TTL 过期 |

情景记忆预热规则：

- 第一轮对话从 `zr_episodic_logs` 拉取最近 5 条。
- 后续对话从 `session:{user_id}:{session_id}:context` 读取。
- 每轮对话结束先写 Redis。
- 会话空闲 5 分钟后写入 `zr_episodic_logs`。

语义记忆预热规则：

- 第一轮从 `zr_semantic_memories` 加载。
- 只加载 `confidence >= 0.6` 或最近 7 天访问过的语义记忆。
- 按 `confidence` 排序。
- 每个用户最多加载 50 条。
- 必须过滤 `deleted_at IS NULL`。
- 后续对话从 `user:{user_id}:semantic` 读取。

### 验收标准

- Retriever 每轮回答前优先读取 Redis 上下文和语义记忆。
- Redis 语义记忆缓存不能绕过 `user_id`。
- Redis 中的情景/语义记忆最终必须落库或自然过期。

## 5. LLM 缓存

### 背景

重复的模型请求会浪费 token 和时间，部分稳定 prompt 可以短期缓存。

### 决策

LLM 缓存使用模型名和 prompt hash 组成 key。缓存只保存可复用的非敏感结果，不保存用户隐私原文和认证信息。

### 实现要点

| 用途 | Key | Owner | 内容 | TTL | 过期设计 |
|---|---|---|---|---|---|
| LLM 响应缓存 | `llm:cache:{model}:{prompt_hash}` | `core/task_redis` | 模型响应文本 | 7 天 | TTL 到期自动删除 |

### 验收标准

- prompt hash 不应泄露原始 prompt。
- 含敏感信息、用户隐私或强时效内容的 LLM 请求不进入缓存。

## 6. Celery 缓存

### 背景

Celery 使用 Redis 作为 broker / backend，会产生内部任务结果 key。

### 决策

Celery 内部 key 由 Celery 管理，业务代码不直接读写。

### 实现要点

| 用途 | Key | Owner | 内容 | TTL | 过期设计 |
|---|---|---|---|---|---|
| Celery 任务结果 | `celery-task-meta-*` | `celery` | Celery result backend 元数据 | Celery 配置控制 | 由 Celery 管理 |

### 验收标准

- 业务代码不依赖 Celery 内部 key 作为业务状态来源。
- 任务业务状态以 `task:{task_id}:*` 和 PostgreSQL 为准。

## 7. 全局过期策略

### 背景

不同缓存承载的业务生命周期不同，不能统一使用一个 TTL。

### 决策

按业务生命周期设定 TTL，短会话短 TTL，任务状态按任务频率设置，认证状态按 token 生命周期设置。

### 实现要点

| 类型 | TTL |
|---|---|
| 游客 Session | 7 天，读取时刷新 |
| Refresh Token | 与 refresh token 有效期一致，当前为 7 天 |
| Access Token 黑名单 | access token 剩余寿命 |
| 验证码 | 300 秒，验证成功删除 |
| 一次性任务工作区 | 1 小时 |
| 周期任务工作区 | 30 天 |
| 报告版本序列 | 2 天 |
| Retriever 会话上下文 | 30 分钟 |
| Retriever 语义记忆缓存 | 30 分钟 |
| Retriever 工作日志 | 30 分钟 |
| LLM 响应缓存 | 7 天 |
| Celery 结果 | Celery 配置控制 |

### 验收标准

- 任何新增 Redis key 都必须显式说明 TTL。
- 任何长期事实都必须落 PostgreSQL。
- Redis key 过期不应导致用户长期数据丢失。

## 8. 已确认决策

1. `refresh_token:{user_id}` 暂时保存当前有效 refresh token 原值，不做 hash 存储。
2. `captcha:{token}` 默认 TTL 固定为 300 秒，对应 `backend/config.toml` 的 `app.captcha_ttl_seconds`。
