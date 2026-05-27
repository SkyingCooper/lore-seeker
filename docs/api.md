# API 设计

## 认证方案

采用 JWT Bearer Token，支持两种身份：

| 身份 | 获取方式 | 标识字段 |
|---|---|---|
| 游客 | `POST /auth/guest`，传入浏览器指纹 | `fingerprint` |
| 注册用户 | `POST /auth/register` 或 `POST /auth/login` | `email` |

Token 有效期：10080 分钟（7 天），通过 `config.toml` 的 `[app] jwt_expire_minutes` 配置。

所有需要认证的接口在 Header 中携带：
```
Authorization: Bearer <token>
```

## 接口规范

### 认证模块

| 方法 | 路径 | 请求体 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/guest` | `{fingerprint}` | 游客登录，指纹不存在则自动注册 |
| POST | `/api/v1/auth/register` | `{email, password}` | 邮箱注册 |
| POST | `/api/v1/auth/login` | form-data `username/password` | 登录（OAuth2 标准格式） |

**响应**（统一）：
```json
{
  "access_token": "eyJ...",
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

| HTTP 状态码 | 场景 |
|---|---|
| 400 | 请求参数错误（邮箱已注册、密码错误等） |
| 401 | 未携带 Token 或 Token 无效/过期 |
| 403 | 无权访问他人资源 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

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
