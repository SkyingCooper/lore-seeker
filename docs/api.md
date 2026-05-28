# API 设计

## 认证方案

采用 JWT Bearer Token + Refresh Token 双令牌机制，支持两种身份：

| 身份 | 获取方式 | 标识字段 |
|---|---|---|
| 游客 | `POST /auth/guest`，传入浏览器指纹 | `fingerprint` |
| 注册用户 | `POST /auth/register` 或 `POST /auth/login` | `email` |

**令牌机制**：
- **access token**：30 分钟有效期，JWT 含 `jti`（唯一标识），用于 API 鉴权
- **refresh token**：7 天有效期，JWT 含 `jti`（唯一标识），存 Redis `refresh_token:{user_id}`，用于无感续期
- **轮换策略**：每次 `/refresh` 或重新登录都会轮换 refresh token，旧 token 立即失效
- **登出**：access token 的 `jti` 加入 Redis 黑名单，存活期内拒绝使用

## 接口规范

### 认证模块

| 方法 | 路径 | 请求体 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/guest` | `{fingerprint}` | 游客登录，指纹不存在则自动注册 |
| POST | `/api/v1/auth/register` | `{email, password}` | 邮箱注册（密码须含字母+数字，8 位起） |
| POST | `/api/v1/auth/login` | form-data `username/password` | 登录（OAuth2 标准格式） |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | 刷新 access token（旧 refresh token 被轮换） |
| POST | `/api/v1/auth/logout` | Header `Authorization: Bearer <token>` | 登出，access token 加入黑名单 |
| POST | `/api/v1/auth/upgrade` | `{fingerprint, email, password}` | 游客升级为注册用户 |

**登录/注册/刷新响应**（统一）：
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "uuid",
  "is_guest": false
}
```

### 用户模块

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/users/me` | 获取当前用户信息和偏好 |
| PATCH | `/api/v1/users/me/preferences` | 更新用户偏好（JSON merge） |

### 搜索模块

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/search/topics` | 获取用户主题列表 |
| POST | `/api/v1/search/topics` | 创建主题 |
| POST | `/api/v1/search/start` | 启动搜索任务（异步，立即返回 task_id） |
| GET | `/api/v1/search/tasks/{id}` | 查询任务状态 |

**启动搜索请求体**：
```json
{
  "query": "Python 异步编程",
  "topic_id": "uuid（可选）",
  "search_mode": "api",
  "target_sites": ["https://docs.python.org"]
}
```

**任务状态响应**：
```json
{
  "task_id": "uuid",
  "status": "pending | running | done | failed",
  "quality_score": 82.0
}
```

### 报告模块

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/reports/` | 获取用户所有报告（按时间倒序） |
| GET | `/api/v1/reports/{id}` | 获取报告完整内容（含 Markdown） |

### 知识检索模块

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/knowledge/query` | 语义检索 + 问答 |

**请求体**：
```json
{
  "query": "Python GIL 是什么",
  "top_k": 5
}
```

**响应**：
```json
{
  "answer": "GIL（全局解释器锁）是...",
  "sources": [
    {"content": "片段前200字...", "report_id": "uuid", "score": 0.92}
  ]
}
```

## 错误码

错误响应格式：`{"detail": {"code": "ERROR_CODE", "detail": "人类可读描述"}}`

| 错误码 | HTTP | 场景 |
|---|---|---|
| `AUTH_INVALID_CREDENTIALS` | 400 | 邮箱或密码错误 |
| `AUTH_EMAIL_EXISTS` | 400 | 邮箱已被注册 |
| `AUTH_WEAK_PASSWORD` | 400 | 密码不满足强度要求 |
| `AUTH_TOKEN_EXPIRED` | 401 | Token 过期或无效 |
| `AUTH_TOKEN_BLACKLISTED` | 401 | Token 已被登出撤销 |
| `AUTH_REFRESH_INVALID` | 401 | Refresh token 无效或已被轮换 |
| `AUTH_NOT_AUTHENTICATED` | 401 | 未携带 Token |
| `GUEST_NOT_FOUND` | 404 | 游客指纹不存在 |
| `GUEST_ALREADY_REGISTERED` | 400 | 该游客已是注册用户 |

## 相关文件

- `backend/api/v1/auth.py`
- `backend/api/v1/users.py`
- `backend/api/v1/search.py`
- `backend/api/v1/reports.py`
- `backend/api/v1/knowledge.py`

---

## 2025-05-27 — 初始设计

**背景**：确定 API 结构和认证方案。

**决策**：
- 游客登录使用浏览器指纹而非 session，方便前端无感知持久化身份
- 搜索任务异步执行，API 只返回 task_id，前端轮询状态（3 秒间隔）
- 登录接口使用 OAuth2 标准 form-data 格式，兼容 FastAPI 自动生成的 `/docs` 测试界面

**待解决**：
- 任务状态推送目前依赖轮询，后续可升级为 WebSocket
- 报告列表未做分页，数据量大时需要添加 `limit/offset`

**影响范围**：`api/v1/` 所有文件

---

## 2026-05-28 — 认证模块完整实现

**背景**：基础认证端点只支持简单的 JWT 签发，缺少令牌刷新、登出失效、密码校验等安全机制。

**决策**：
- 采用双令牌机制（access 30min + refresh 7d），refresh token 存 Redis 支持轮换和撤销
- 登出时 access token 的 jti 加入 Redis 黑名单（TTL=剩余有效期）实现即时失效
- 密码校验要求至少 8 位、包含字母和数字
- 游客升级通过 `POST /auth/upgrade`，携带 fingerprint + email + password，关联已有数据
- 统一错误码格式 `{code, detail}`，前端可据此处理（如 `AUTH_TOKEN_EXPIRED` 触发自动刷新）

**放弃的方案**：
- 纯无状态 JWT（放弃主动失效能力，登出后 token 仍可用到过期）
- refresh token 存数据库（Redis 的 TTL 自动过期更省资源）

**影响范围**：`api/v1/auth.py`、`core/security.py`（新建）、`core/redis_client.py`（新建）、`core/config.py`（fix env_file 路径）、`frontend/src/stores/auth.ts`、`requirements.txt`（pin bcrypt<5）
