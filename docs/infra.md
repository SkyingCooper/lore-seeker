# 基础设施

## Docker Compose 服务拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ frontend │    │ backend  │    │  worker  │              │
│  │  :5173   │    │  :8000   │    │ (celery) │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                      │
│       │         ┌─────▼───────────────▼──┐                  │
│       │         │         redis          │                   │
│       │         │         :6379          │                   │
│       │         └────────────────────────┘                   │
│       │                   │                                   │
│       │         ┌─────────▼──────────────┐                   │
│       └────────▶│          db            │                   │
│                 │   postgresql :5432     │                   │
│                 └────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

## 服务说明

| 服务 | 镜像 | 端口 | 说明 |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL + pgvector 扩展 |
| `redis` | `redis:7-alpine` | 6379 | Celery broker + backend |
| `backend` | 本地构建 | 8000 | FastAPI，`--reload` 热重载 |
| `worker` | 本地构建（同 backend） | — | Celery worker，监听 `agent_tasks` 队列 |
| `frontend` | 本地构建 | 5173 | Vite dev server，`--host 0.0.0.0` |

`backend` 和 `worker` 共用同一个 Dockerfile，挂载同一份代码（`./backend:/app`），区别只在启动命令。

## 健康检查

`db` 和 `redis` 配置了 healthcheck，`backend` 和 `worker` 通过 `depends_on: condition: service_healthy` 等待依赖就绪后再启动，避免启动顺序问题。

## 数据持久化

PostgreSQL 数据通过 named volume `pgdata` 持久化，`docker compose down` 不会删除数据。

删除数据：`docker compose down -v`（谨慎操作）

## 数据库初始化

`backend/db/init.sql` 在容器首次启动时执行，启用 `vector` 和 `uuid-ossp` 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

表结构由 SQLAlchemy 的 `Base.metadata.create_all()` 在 FastAPI 启动时自动创建（`lifespan` 事件）。

## 本地开发

```bash
# 启动所有服务
docker compose up --build

# 只启动依赖（db + redis），后端本地运行
docker compose up db redis

# 查看 worker 日志
docker compose logs -f worker

# 重建单个服务
docker compose up --build backend
```

## 相关文件

- `docker-compose.yml` — 服务编排
- `backend/Dockerfile` — 后端镜像（含 Playwright 依赖）
- `frontend/Dockerfile` — 前端镜像
- `backend/db/init.sql` — 数据库初始化

---

## 2025-05-27 — 初始设计

**背景**：确定部署方案，要求一键启动，开发体验友好。

**决策**：
- `backend` 和 `worker` 共用镜像，减少构建时间
- 代码目录挂载为 volume，支持热重载，无需每次改代码都重建镜像
- 使用 `pgvector/pgvector` 官方镜像，避免手动安装扩展

**待解决**：
- 生产环境需要去掉 `--reload`，配置 gunicorn 多进程
- 前端生产环境需要 `npm run build` + nginx 静态服务，当前 Dockerfile 只适合开发

**影响范围**：`docker-compose.yml`、`backend/Dockerfile`、`frontend/Dockerfile`
