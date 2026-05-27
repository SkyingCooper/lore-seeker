---
name: lore-seeker-project-overview
description: lore-seeker 项目的技术选型、架构决策和关键配置约定
metadata:
  type: project
---

多 Agent 知识库系统，项目路径：/Users/coopergin/Project/python_work/lore-seeker

**Why:** 用户需要一个能自动搜索、整理、入库、检索知识的系统，支持多 LLM 厂商和多搜索方式。

**How to apply:** 修改任何模块前先确认当前架构约定。

## 技术栈
- 后端：Python 3.12 + FastAPI + LangGraph + PostgreSQL(pgvector) + Celery + Redis
- 前端：Vue 3 + TypeScript + Vite + md-editor-v3（Markdown 渲染）
- 部署：Docker Compose

## 关键架构决策
- LLM 路由：`backend/core/llm_router.py`，通过 `DEFAULT_LLM_PROVIDER` 环境变量切换 deepseek/gemini/openai，全部走 OpenAI 兼容接口
- Embedding/Reranker 路由：`backend/core/embedding_router.py`，支持 dashscope（阿里云百炼）/ openai / jina
- 搜索服务：`backend/services/search_service.py`，支持 tavily/serpapi/bing API + Playwright 爬虫，由 `search_mode` 字段控制（api/crawl/both）
- Agent 编排：LangGraph 有向图，planner → searcher → organizer → quality_check，质检不通过最多重试 3 次
- 异步任务：Celery worker 执行 Agent 图，FastAPI 只负责触发和状态查询
- 向量存储：pgvector，切片策略按 Markdown 标题分段，超长段落滑窗切割（800字符，100重叠）

## 环境变量
所有配置在 `.env.example`，复制为 `.env` 后填入 API Key 即可启动

## 数据库模型
User → Topic（主题配置）→ SearchTask → Report → KnowledgeChunk（含 vector 列）

## SDD 规范
每次需求补充或变更，必须同步更新 `docs/` 目录下对应的 md 文件：
- 新功能 → 在对应模块文件顶部追加变更记录（背景 / 决策 / 放弃的方案 / 影响范围）
- 跨模块变更 → 同时更新 `docs/overview.md` 和各相关模块文件
- 新模块 → 新建 `docs/<module>.md`，并在 `docs/README.md` 索引中添加条目
- 文件映射：agent-planner / agent-searcher / agent-organizer / agent-retriever / storage / api / frontend / config / infra / overview
