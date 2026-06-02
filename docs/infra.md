# 基础设施设计

## 1. 模块职责

基础设施文档定义本地开发和容器启动方式，包括数据库、Redis、后端、worker 和前端。

对应文件：

- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `backend/db/schema.sql`
- `tests/infra/test_connections.py`

## 2. Docker Compose 拓扑

### 背景

开发环境需要一条命令启动完整依赖，并保持前后端热更新。

### 决策

使用 Docker Compose 编排五个服务。

### 实现要点

| 服务 | 端口 | 职责 |
|---|---:|---|
| `db` | 5432 | PostgreSQL + pgvector |
| `redis` | 6379 | Celery、Session、Token、任务状态 |
| `backend` | 8000 | FastAPI |
| `worker` | 无 | Celery worker |
| `frontend` | 5173 | Vite dev server |

依赖关系：

```text
frontend -> backend -> db / redis
worker -> db / redis
```

### 验收标准

- `docker compose up --build` 可启动完整开发环境。
- `db` 和 `redis` healthcheck 通过后，backend 和 worker 再启动。
- PostgreSQL 数据通过 `pgdata` volume 持久化。

## 3. 数据库初始化

### 背景

数据库首次启动需要创建扩展和表结构。

### 决策

初始化文件统一为 `backend/db/schema.sql`。

### 实现要点

- Compose 将 `./backend/db/schema.sql` 挂载进 `/docker-entrypoint-initdb.d/schema.sql`。
- `schema.sql` 启用 `vector` 扩展。
- 表结构也可由 FastAPI lifespan 中的 `Base.metadata.create_all()` 创建。

### 验收标准

- 新建 volume 后数据库可完成初始化。
- pgvector 扩展可用。

## 4. 本地开发

### 背景

开发时需要既能全容器运行，也能只启动依赖、本地运行前后端。

### 决策

支持两种开发方式。

### 实现要点

完整容器：

```bash
docker compose up --build
```

只启动依赖：

```bash
docker compose up db redis
```

后端本地：

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

前端本地：

```bash
cd frontend
npm run dev
```

### 验收标准

- 前端 Vite 代理能访问后端 8000。
- worker 能连接 Redis 和数据库。
- 本地 `.env` 能被后端正确加载。

## 5. 验证

### 背景

连接错误和 secrets 泄露需要尽早发现。

### 决策

基础设施连接使用独立脚本验证。

### 实现要点

```bash
.venv/bin/python tests/infra/test_connections.py
```

验证内容：

- PostgreSQL 连接。
- pgvector 扩展。
- 表数量。
- Redis 连接。
- Redis key 数量。

### 验收标准

- 脚本从 `.env` 读取连接信息。
- 输出不打印完整连接串和密码。
- 连接失败时返回非零退出码。
