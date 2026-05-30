# API 设计

## 认证方案

采用 **Session Cookie（游客）+ JWT Bearer Token（注册用户）** 双通道认证。

### 认证流程图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        首次访问（无 Session Cookie）                   │
│                                                                       │
│  前端 POST /api/v1/auth/guest                                         │
│       │                                                               │
│       ▼                                                               │
│  后端  生成 session_id = uuid4()                                      │
│       Redis SET session:{id} = {user_id, is_guest, ...}  TTL=7d      │
│       DB 创建 guest User 记录                                         │
│       Set-Cookie: session_id=xxx; HttpOnly; Secure; Max-Age=604800    │
│       │                                                               │
│       ▼                                                               │
│  前端  收到 Cookie，成为游客（只读权限）                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    再次访问（有 Session Cookie）                       │
│                                                                       │
│  前端请求自动带 Cookie: session_id=xxx                                 │
│       │                                                               │
│       ▼                                                               │
│  后端  从 Redis 读取 session，校验有效性                                │
│       刷新 TTL，更新 last_access_at                                    │
│       │                                                               │
│       ▼                                                               │
│  返回只读内容                                                          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        用户登录（账号密码）                             │
│                                                                       │
│  前端 POST /api/v1/auth/login                                         │
│       Body: username=email&password=xxx (form-urlencoded)              │
│       如果带了游客 SessionID：记录日志，不合并数据，不删除 session        │
│       │                                                               │
│       ▼                                                               │
│  后端  验证账号密码 ✅                                                  │
│       生成 JWT access_token (30min) + refresh_token (7d)               │
│       │                                                               │
│       ▼                                                               │
│  前端  保存 token 到 localStorage                                      │
│       后续请求 Header: Authorization: Bearer <token>                   │
│       重新加载页面，以用户身份展示                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     访问受保护接口                                    │
│                                                                       │
│  前端 Header: Authorization: Bearer <token>                           │
│       │                                                               │
│       ▼                                                               │
│  后端  提取 Token → 验证有效性                                         │
│       ├── 无效 → 401 Unauthorized                                     │
│       └── 有效 → 从 Token 获取 user_id → 执行业务逻辑                   │
│                                                                       │
│  游客 (Session Cookie) 访问写接口 → 403 GUEST_FORBIDDEN                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                          用户退出                                     │
│                                                                       │
│  前端  清除 localStorage 中的 token                                    │
│       可选 POST /api/v1/auth/logout（JWT 黑名单 + Session 清除）       │
│       刷新页面 → 回到游客模式                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 认证方式对比

| 身份 | 获取方式 | 凭证 | 权限 |
|---|---|---|---|
| 游客 | `POST /auth/guest` | Session Cookie (HttpOnly) | 只读：浏览报告 |
| 注册用户 | `POST /auth/register` 或 `POST /auth/login` | JWT Bearer Token | 读写：搜索、创建、管理 |

**JWT 令牌机制**：
- **access token**：30 分钟有效期，含 `jti`（唯一标识），用于 API 鉴权
- **refresh token**：7 天有效期，存 Redis `refresh_token:{user_id}`，用于无感续期
- **轮换策略**：每次 `/refresh` 或重新登录都会轮换 refresh token，旧 token 立即失效
- **登出**：access token 的 `jti` 加入 Redis 黑名单，存活期内拒绝使用

**Session Cookie 机制**：
- **session_id**：UUID，存 Redis `session:{id}`，TTL 7 天
- **刷新策略**：每次访问自动刷新 TTL 和 `last_access_at`
- **安全性**：`HttpOnly; Secure; SameSite=Lax; Path=/`
- **退出**：调用 `/logout` 或自然过期

## 接口规范

### 认证模块

| 方法 | 路径 | 请求体 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/guest` | 无 | 游客登录，创建 User + Session Cookie |
| POST | `/api/v1/auth/register` | `{username, email, password}` | 注册（密码须含字母+数字，8 位起） |
| POST | `/api/v1/auth/login` | form-data `username/password` | 登录，username 填用户名或邮箱 |
| POST | `/api/v1/auth/refresh` | `{refresh_token}` | 刷新 access token（旧 refresh token 被轮换） |
| POST | `/api/v1/auth/logout` | Header `Authorization: Bearer <token>` (可选) | 登出，JWT 黑名单 + Session 清除 |
| POST | `/api/v1/auth/upgrade` | `{username, email, password}` | 游客升级为注册用户 |

**游客登录响应**：
```json
{
  "user_id": "uuid",
  "is_guest": true
}
```
同时 `Set-Cookie: session_id=xxx; HttpOnly; Secure; SameSite=Lax; Max-Age=604800; Path=/`

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

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/users/me` | 游客+用户 | 获取当前用户信息和偏好 |
| PATCH | `/api/v1/users/me/preferences` | 仅注册用户 | 更新用户偏好（JSON merge） |

### 搜索模块

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/search/topics` | 游客+用户 | 获取用户主题列表 |
| POST | `/api/v1/search/topics` | 仅注册用户 | 创建主题 |
| POST | `/api/v1/search/start` | 仅注册用户 | 启动搜索任务（异步，立即返回 task_id） |
| GET | `/api/v1/search/tasks/{id}` | 游客+用户 | 查询任务状态 |

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

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/reports/` | 游客+用户 | 获取用户所有报告（按时间倒序） |
| GET | `/api/v1/reports/{id}` | 游客+用户 | 获取报告完整内容（含 Markdown） |

### 知识检索模块

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/knowledge/query` | 仅注册用户 | 语义检索 + 问答 |

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
| `AUTH_NOT_AUTHENTICATED` | 401 | 未携带任何有效凭证 |
| `GUEST_FORBIDDEN` | 403 | 游客无权执行此操作 |
| `GUEST_ALREADY_REGISTERED` | 400 | 当前用户已是注册用户 |

## 相关文件

- `backend/api/v1/auth.py`
- `backend/api/v1/users.py`
- `backend/api/v1/search.py`
- `backend/api/v1/reports.py`
- `backend/api/v1/knowledge.py`
- `backend/core/session.py`
- `backend/core/security.py`

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

---

## 2026-05-30 — 游客认证从 FingerprintJS 迁移到 Session Cookie

**背景**：FingerprintJS 依赖第三方浏览器指纹库，增加了前端包体积和加载延迟。游客登录更适合用标准的服务端 Session Cookie 方案。

**决策**：
- 游客登录改为服务端生成 Session Cookie（HttpOnly; Secure; SameSite=Lax; Max-Age=604800）
- Session 元数据存 Redis（`session:{id}`），每次访问自动刷新 TTL
- 认证依赖拆分为 `get_current_user`（Bearer token 优先，回退 Session cookie）和 `require_member`（拒绝游客）
- 移除 `@fingerprintjs/fingerprintjs` 依赖，简化前端
- 写接口统一加 `require_member` 保护，游客只读
- 升级接口不再依赖 fingerprint，直接从 Session 解析当前游客身份

**放弃的方案**：
- 继续使用 FingerprintJS（依赖重量级，跨浏览器不稳定）
- 纯 JWT 游客（无 Session，前端需自行管理 token，不如 Cookie 透明）

**影响范围**：`api/v1/auth.py`、`core/session.py`（新建）、`api/v1/search.py`、`api/v1/knowledge.py`、`api/v1/users.py`、`frontend/src/stores/auth.ts`、`frontend/src/api/client.ts`、`tests/auth/test_auth_flow.py`
