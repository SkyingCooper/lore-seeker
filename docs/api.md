# API 设计

## 1. 模块职责

API 层负责认证、任务触发、状态查询、报告读取、知识问答和用户偏好管理。长耗时搜索整理流程不在 HTTP 请求内执行，由 Celery worker 异步处理。

对应代码：

- `backend/main.py`
- `backend/api/v1/auth.py`
- `backend/api/v1/captcha.py`
- `backend/api/v1/users.py`
- `backend/api/v1/search.py`
- `backend/api/v1/tasks.py`
- `backend/api/v1/reports.py`
- `backend/api/v1/knowledge.py`

## 2. 认证方案

### 背景

系统需要游客无感访问只读页面，也需要注册用户执行搜索、任务创建、偏好保存等写操作。

### 决策

认证采用双通道：

- 游客：Session Cookie。
- 注册用户：JWT access token + refresh token。

后端认证依赖优先读取 Bearer token，缺失时回退 Session Cookie。

### 实现要点

| 身份 | 凭证 | 权限 |
|---|---|---|
| 游客 | `session_id` HttpOnly Cookie | 只读 |
| 注册用户 | `Authorization: Bearer <access_token>` | 读写 |

接口：

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/guest` | 创建游客 Session |
| POST | `/api/v1/auth/register` | 注册用户 |
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/refresh` | 刷新 access token |
| POST | `/api/v1/auth/logout` | 登出 |
| POST | `/api/v1/auth/upgrade` | 游客升级为注册用户 |

权限依赖：

- `get_current_user`：游客和注册用户均可访问。
- `require_member`：只允许注册用户。

### 验收标准

- 游客访问只读接口成功。
- 游客访问写接口返回 `403 GUEST_FORBIDDEN`。
- access token 过期后前端可用 refresh token 自动续期。
- 登出后本地 token 和服务端状态均失效。

## 3. 用户接口

### 背景

前端需要读取当前用户身份、头像、偏好和账号状态。

### 决策

用户接口集中在 `/api/v1/users`。

### 实现要点

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/users/me` | 游客+用户 | 当前用户信息 |
| PATCH | `/api/v1/users/me/preferences` | 注册用户 | 更新用户偏好 |

用户偏好写入 `zr_user_preferences`，不再依赖 `users.preferences` JSON 字段。

### 验收标准

- 返回数据能驱动前端账户弹层和设置页。
- 游客不能写偏好。

## 4. 主题与快速搜索接口

### 背景

首页需要快速发起一次搜索，同时设置页需要管理主题。

### 决策

`/api/v1/search` 保留为主题管理和快速搜索入口。结构化任务管理使用 `/api/v1/tasks`。

### 实现要点

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/search/topics` | 游客+用户 | 获取主题列表 |
| POST | `/api/v1/search/topics` | 注册用户 | 创建主题 |
| POST | `/api/v1/search/start` | 注册用户 | 快速启动搜索 |
| GET | `/api/v1/search/tasks/{id}` | 游客+用户 | 查询旧任务状态 |

快速搜索请求：

```json
{
  "query": "Python async",
  "topic_id": "可选",
  "search_mode": "mixed",
  "source_sites": ["https://docs.python.org"]
}
```

`search_mode` 合法值：

- `api`
- `crawl`
- `mixed`

### 验收标准

- 无 `topic_id` 时快速搜索自动创建临时主题。
- 有 `topic_id` 时必须校验主题归属当前用户。
- 创建的 `SearchTask.source_sites` 与请求一致。

## 5. 任务接口

### 背景

长期任务、定时任务和任务详情页需要独立任务模型，不能只依赖快速搜索接口。

### 决策

`/api/v1/tasks` 是任务管理主入口。

### 实现要点

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/tasks` | 注册用户 | 创建任务 |
| GET | `/api/v1/tasks` | 游客+用户 | 任务列表 |
| GET | `/api/v1/tasks/{task_id}` | 游客+用户 | 任务详情 |
| POST | `/api/v1/tasks/{task_id}/start` | 注册用户 | 立即执行 |
| POST | `/api/v1/tasks/{task_id}/retry` | 注册用户 | 失败后重试 |
| DELETE | `/api/v1/tasks/{task_id}` | 注册用户 | 逻辑删除 |

创建任务请求：

```json
{
  "topic_id": 1,
  "topic_title": "可选，新主题名称",
  "topic_keywords": ["AI", "LLM"],
  "topic_description": "主题说明",
  "source_sites": ["https://example.com"],
  "search_mode": "mixed",
  "frequency": "once"
}
```

任务列表响应必须包含：

```json
{
  "id": 1,
  "topic_id": 1,
  "topic_title": "主题名称",
  "source_sites": [],
  "search_mode": "mixed",
  "frequency": "once",
  "status": "pending"
}
```

### 验收标准

- `GET /tasks` 返回 `topic_title`。
- 任务只能由所属用户访问。
- `/start` 传给 worker 的配置使用 `source_sites`。
- 状态为 `fetching` 或 `organizing` 时不能重复启动。

## 6. 报告接口

### 背景

前端需要报告列表、报告详情、任务关联报告和用户反馈。

### 决策

报告接口集中在 `/api/v1/reports`。

### 实现要点

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/v1/reports/` | 游客+用户 | 当前用户报告列表 |
| GET | `/api/v1/reports/?task_id=1` | 游客+用户 | 指定任务报告 |
| GET | `/api/v1/reports/{report_id}` | 游客+用户 | 报告详情 |
| POST | `/api/v1/reports/{report_id}/evaluate` | 注册用户 | 满意度反馈 |

查询报告必须通过 `reports.task_id -> search_tasks.user_id` 校验归属。

### 验收标准

- 用户不能读取其他用户报告。
- 报告详情返回 `content_md`、`toc`、`summary`、评分和状态。
- 满意度只能由报告所属用户提交。

## 7. 知识接口

### 背景

注册用户需要对自己的知识库进行语义问答。

### 决策

知识问答接口仅允许注册用户访问，并在检索 SQL 层按用户隔离。

### 实现要点

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/v1/knowledge/query` | 注册用户 | 语义检索 + RAG 回答 |

请求：

```json
{
  "query": "GIL 是什么",
  "top_k": 5
}
```

响应：

```json
{
  "answer": "回答正文",
  "sources": [
    {"content": "片段前 200 字", "report_id": "1", "score": 0.92}
  ]
}
```

### 验收标准

- 游客访问返回 403。
- 查询只命中当前用户任务产生的切片。
- 返回来源片段和报告 ID。

## 8. 错误码

### 背景

前端需要稳定识别认证、权限和任务状态错误。

### 决策

错误响应格式统一为：

```json
{
  "detail": {
    "code": "ERROR_CODE",
    "detail": "可读错误信息"
  }
}
```

### 实现要点

常用错误码：

| 错误码 | HTTP | 场景 |
|---|---:|---|
| `AUTH_INVALID_CREDENTIALS` | 400 | 账号或密码错误 |
| `AUTH_EMAIL_EXISTS` | 400 | 邮箱已注册 |
| `AUTH_WEAK_PASSWORD` | 400 | 密码强度不足 |
| `AUTH_TOKEN_EXPIRED` | 401 | access token 过期 |
| `AUTH_REFRESH_INVALID` | 401 | refresh token 无效 |
| `AUTH_NOT_AUTHENTICATED` | 401 | 未认证 |
| `GUEST_FORBIDDEN` | 403 | 游客访问写接口 |
| `TASK_RUNNING` | 400 | 任务已运行 |
| `TASK_NOT_FAILED` | 400 | 非失败任务不能重试 |

### 验收标准

- 前端可根据 `code` 做刷新 token、跳转登录或展示错误。
- 新接口不得返回无法解析的纯字符串错误。

## 9. 已确认待调整

- `/api/v1/search/start` 和 `/api/v1/tasks` 的长期职责边界后续单独收敛；当前两者都已接入 `ContractValidationMiddleware`，统一校验 `source_sites`、`search_mode` 和必填业务字段。
