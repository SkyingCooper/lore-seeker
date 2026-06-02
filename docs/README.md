# Lore Seeker 设计文档索引

`DESIGN_SUMMARY.md` 是宏观架构入口；模块细节以各自文档为准。修改系统设计时，先确认影响范围，再更新对应模块文档。

## 文档地图

| 文件 | 层级 | 主要内容 |
|---|---|---|
| [DESIGN_SUMMARY.md](./DESIGN_SUMMARY.md) | 全局总览 | 系统目标、技术架构、模块边界、跨模块约定 |
| [overview.md](./overview.md) | 系统架构 | 主链路、模块边界、异步任务模型、全局字段 |
| [api.md](./api.md) | 后端 API | 认证、用户、主题、任务、报告、知识接口、错误码 |
| [storage.md](./storage.md) | 存储 | PostgreSQL、pgvector、Redis、Agent 记忆表 |
| [agent-planner.md](./agent-planner.md) | Agent | 任务规划、质量检查、State 约定 |
| [agent-searcher.md](./agent-searcher.md) | Agent | 搜索模式、搜索 API、爬虫、去重 |
| [agent-organizer.md](./agent-organizer.md) | Agent | Markdown 报告、TOC、报告入库 |
| [agent-retriever.md](./agent-retriever.md) | Agent | 向量召回、用户隔离、重排序、RAG 回答 |
| [agent-boundaries.md](./agent-boundaries.md) | Agent 约束 | 四个 Agent 的能力、数据、职责、权限、生命周期边界 |
| [agent-guardrails.md](./agent-guardrails.md) | Agent 护栏 | Pydantic AI 护栏 hook、校验模型、接入点 |
| [frontend.md](./frontend.md) | 前端 | 技术栈、路由、主布局、状态、任务页、报告页 |
| [config.md](./config.md) | 配置 | TOML、`.env`、环境变量优先级、Provider 路由 |
| [prompts.md](./prompts.md) | Prompt 配置 | Markdown 提示词目录、prompt-id、加载方式 |
| [infra.md](./infra.md) | 基础设施 | Docker Compose、数据库初始化、本地验证 |
| [constraints.md](./constraints.md) | 约束接口 | Agent、Tool、Redis、DB contract 铁律 |

## 写作规则

1. `DESIGN_SUMMARY.md` 只写宏观架构，不展开模块细节。
2. 具体方案写入对应模块文档，不跨文件拆散同一方案。
3. 每个方案按“背景 -> 决策 -> 实现要点 -> 验收标准”组织。
4. 已确认但未完成的内容集中写入“已确认待实现”。
5. 不确定内容标记为 `[待确认]`，并在文件末尾汇总。
6. 不记录历史流水账，不保留废弃方案说明。
7. Agent、Tool、Redis/DB 交互必须先定义 contract，再写业务代码。


## 验证命令

```bash
python3 -m compileall -q backend
cd frontend && npm run build
```
