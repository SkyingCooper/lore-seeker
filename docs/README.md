# Lore Seeker — 设计文档索引

本目录存放系统各模块的软件设计文档（SDD）。每次功能迭代、架构决策或接口变更后，在对应文件中追加记录。

## 文档列表

| 文件 | 模块 | 说明 |
|---|---|---|
| [overview.md](./overview.md) | 系统总览 | 整体架构、模块关系、数据流 |
| [agent-planner.md](./agent-planner.md) | 规划 Agent | P&E 推理设计、质检循环、个性化记忆 |
| [agent-searcher.md](./agent-searcher.md) | 搜索 Agent | 搜索模式、爬虫策略、去重逻辑 |
| [agent-organizer.md](./agent-organizer.md) | 整理 Agent | Markdown 生成、TOC 提取、切片策略 |
| [agent-retriever.md](./agent-retriever.md) | 检索 Agent | 向量检索、重排序、问答生成 |
| [storage.md](./storage.md) | 存储层 | 三层存储设计、数据模型、向量索引 |
| [api.md](./api.md) | API 设计 | 接口规范、认证方案、错误码 |
| [frontend.md](./frontend.md) | 前端 | 页面结构、组件设计、状态管理 |
| [config.md](./config.md) | 配置系统 | TOML + .env 分层设计、优先级规则 |
| [infra.md](./infra.md) | 基础设施 | Docker Compose 服务拓扑、部署说明 |

## 记录规范

每个文档内按时间倒序追加变更记录，格式：

```
## YYYY-MM-DD — 变更标题

**背景**：为什么做这个改动
**决策**：做了什么，选择了哪个方案
**放弃的方案**：考虑过但未采用的方案及原因
**影响范围**：涉及哪些文件 / 接口 / 数据结构
```
