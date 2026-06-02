# Celery 调度设计

## 1. 模块职责

Celery 负责异步任务执行、周期任务调度和后台清理任务。Redis 同时作为 Celery broker 和 result backend，但业务状态仍以 PostgreSQL 和 `task:{task_id}:*` Redis 工作区为准。

对应配置：

- `config/celery.yaml`
- Redis 连接配置：`.env` / `backend/config.toml`

## 2. Celery 基础约定

### 背景

搜索、爬取、整理、记忆淘汰和周期任务触发都可能耗时较长，不能阻塞 FastAPI 请求线程。

### 决策

Celery 使用 Redis 作为消息队列和结果存储：

- broker：Redis
- result backend：Redis
- beat scheduler：Celery Beat
- worker：执行搜索任务、周期任务启动、记忆淘汰等后台任务

### 实现要点

- FastAPI 只负责创建任务和返回任务 ID。
- Celery worker 执行长任务。
- 任务执行中的业务状态写入 `task:{task_id}:*` 工作区。
- Celery 内部 key 不作为业务事实来源。

### 验收标准

- API 请求不会等待搜索/梳理完整执行完成。
- Celery 任务失败时，业务任务状态能同步更新。
- Redis 中 Celery 内部 key 不被业务代码直接依赖。

## 3. 定时任务

### 背景

系统存在两类定时任务：系统维护任务和用户配置的重复搜索任务。二者都需要可配置调度策略。

### 决策

定时调度参数统一放入 `config/celery.yaml`，不得写死在 worker 或 Agent 代码里。

### 实现要点

1. 记忆淘汰

1.1 每天夜里 `02:00` 触发。

1.2 由 Celery Beat 生成任务。

1.3 任务调用记忆管理子 Agent，执行语义记忆、情景记忆和 Skill 有效性管理。

2. 重复搜索任务

2.1 支持 `daily / weekly / biweekly / monthly`。

2.2 到期后触发新的搜索任务启动，而不是复用旧任务 ID。

2.3 新任务继承主题、关键词、source_sites、search_mode 和用户配置。

2.4 当前日期内的报告 `sequence` 可通过 Redis 递增 key 实现，避免并发生成重复版本号。

3. 任务超时与重试

3.1 任务软超时、硬超时、最大重试次数和退避策略都进入配置文件。

3.2 搜索子任务、梳理任务、记忆清理任务可以使用不同超时策略。

### 验收标准

- 记忆淘汰任务可按配置在 `02:00` 触发。
- 重复搜索任务不会覆盖历史任务。
- 修改调度频率、超时和重试策略不需要改业务代码。

## 4. 配置项

### 背景

Celery 调度和执行参数属于运行策略，必须可配置。

### 决策

配置文件固定为 `config/celery.yaml`。

### 实现要点

配置分组：

- `broker`：Redis broker/backend 说明。
- `beat.memory_eviction`：记忆淘汰 cron。
- `beat.periodic_search_dispatcher`：重复任务扫描间隔。
- `task_defaults`：全局超时、重试和结果过期时间。
- `task_routes`：不同后台任务的队列与超时策略。
- `memory_policy`：记忆淘汰阈值。

详细参数以 `config/celery.yaml` 为准。

### 验收标准

- 所有 Celery 调度参数能在配置文件中找到。
- 新增周期任务前必须先补配置和本文档。

## 5. 建议补充

当前方案还建议同步补充以下能力：

1. Celery 任务幂等键，避免 Beat 重复触发同一周期任务。
2. 任务锁，例如 `celery:lock:{job_name}:{date}`，防止多 worker 并发执行同一个维护任务。
3. 失败告警归档，将关键后台任务失败写入审计表或工作日志。
4. 周期任务扫描窗口，例如每 5 分钟扫描未来 5 分钟内应触发的任务。
