# Lore Seeker

> 多 Agent 知识库系统，自动搜索、整理、检索网络知识。

[English](./README.md)

## 项目简介

Lore Seeker 是一个由 LangGraph 编排的多 Agent 知识库系统。它的核心思路是：**让 AI 代替人完成"读网页 → 提炼知识 → 建立体系"这条链路**，并将结果沉淀为可持续检索的个人知识库。

用户只需描述一个主题，系统就会自动完成搜索、过滤、编排、入库，最终生成一份带目录的 Markdown 知识文档，并支持后续的自然语言问答。

---

## 系统架构

### Agent 流水线

```
用户查询
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│                        规划 Agent (Planner)                       │
│  P&E 推理：Perception → 理解意图、拆解子查询、预判知识结构         │
│           Evaluation → 质检评分、反馈驱动重试、记录用户偏好        │
└────────────────────────────┬─────────────────────────────────────┘
                             │ 搜索计划（子查询 + 预期章节）
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                        搜索 Agent (Searcher)                      │
│  API 模式：Tavily / SerpAPI / Bing，支持指定域名过滤               │
│  爬虫模式：Playwright 无头浏览器，抓取指定网站全文                  │
│  混合模式：API 先行，爬虫补充深度内容                               │
└────────────────────────────┬─────────────────────────────────────┘
                             │ 原始结果（title + url + content）
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       整理 Agent (Organizer)                      │
│  过滤低质量内容，按相关性聚类，生成结构化 Markdown                  │
│  自动提取 TOC（章 / 节层级），输出 YAML front matter               │
└────────────────────────────┬─────────────────────────────────────┘
                             │ Markdown 文档 + TOC
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                   质检节点 (规划 Agent · Evaluation)               │
│  对文档打分（0-100），score ≥ 75 视为通过                          │
│  不通过则将反馈注入 Organizer 重新生成，最多重试 3 次               │
└────────────────────────────┬─────────────────────────────────────┘
                             │ 通过
                             ▼
                      三层存储（见下文）
```

### 规划 Agent 的 P&E 推理

规划 Agent 是整个系统的"大脑"，承担两个阶段的推理：

**Perception（感知与规划）**
- 理解用户原始意图，识别模糊表达并补全语义
- 将单一查询拆解为多个子查询，覆盖主题的不同维度
- 预判知识体系结构（预期章节），为整理 Agent 提供方向约束
- 结合用户历史偏好（`preferences` 字段）调整搜索策略

**Evaluation（评估与反馈）**
- 对整理 Agent 输出的 Markdown 文档进行多维度评分：内容完整性、结构清晰度、信息准确性
- 生成具体的改进反馈，注入下一轮整理，形成闭环
- 记录每次任务的质量分数，逐步积累用户的内容偏好模型

```
Perception                          Evaluation
──────────────────────────          ──────────────────────────
用户意图 → 子查询列表               Markdown → 质量评分
历史偏好 → 搜索策略调整             评分反馈 → 重试指令
预期结构 → 章节约束                 通过记录 → 偏好更新
```

### 存储架构

**三层基础存储**

```
┌─────────────────────────────────────────────────────────────┐
│  第一层：关系层（PostgreSQL）                                  │
│  存储结构化元数据：用户、主题、任务、报告                        │
│  支持按时间、质量分、主题等维度查询历史记录                      │
├─────────────────────────────────────────────────────────────┤
│  第二层：向量层（pgvector）                                    │
│  报告切片 + 语义记忆，独立向量化                                │
│  支持余弦相似度检索，配合重排序模型精排 Top-K 结果              │
│  向量维度可配置（DashScope text-embedding-v3 默认 1536 维）    │
├─────────────────────────────────────────────────────────────┤
│  第三层：缓存层（Redis）                                       │
│  Celery 任务队列：异步执行 Agent 流水线，不阻塞 API 响应        │
│  工作记忆活跃态：存储当前会话目标、步骤和工具缓存                │
└─────────────────────────────────────────────────────────────┘
```

**Agent 五类记忆层（均持久化在 PostgreSQL）**

```
┌──────────────┬─────────────────────────────────────────────────────────┐
│  工作记忆    │  当前目标、执行步骤、工具调用缓存                         │
│              │  活跃时存 Redis，会话结束后异步归档到 DB，Redis 中删除    │
├──────────────┼─────────────────────────────────────────────────────────┤
│  情景记忆    │  流水账日记，记录每次对话和任务执行的完整过程              │
├──────────────┼─────────────────────────────────────────────────────────┤
│  语义记忆    │  提炼的知识规律；embedding 对 summary 计算，按需加载全文  │
├──────────────┼─────────────────────────────────────────────────────────┤
│  用户偏好    │  显式/隐式配置，key-value 形式，含置信度追踪              │
├──────────────┼─────────────────────────────────────────────────────────┤
│  Skill 记忆  │  操作 SOP；三层结构（title/content/citation）按需加载    │
└──────────────┴─────────────────────────────────────────────────────────┘
```

报告检索流程：
1. 用户提问 → 向量层召回 Top-20 候选 chunks
2. 重排序模型精排 → 取 Top-5
3. 关系层补充报告元数据（标题、来源、时间）
4. LLM 基于上下文生成最终回答

---

## 功能特性

- **P&E 双阶段规划** — 感知阶段拆解任务，评估阶段质检闭环，最多 3 轮自动优化
- **多 Agent 流水线** — 规划、搜索、整理、检索各司其职，LangGraph 有向图编排
- **灵活的 LLM 路由** — 支持 DeepSeek、Gemini、OpenAI，通过 `config.toml` 一行切换
- **双搜索模式** — 搜索 API（Tavily / SerpAPI / Bing）和 Playwright 爬虫，可混合使用，支持指定目标网站
- **三层基础存储** — 关系层 + 向量层 + 缓存层，兼顾结构化查询与语义检索
- **可配置的向量与重排序** — 支持阿里云百炼（DashScope）、OpenAI、Jina，配置文件切换
- **五类 Agent 记忆** — 工作记忆（Redis 活跃态 + DB 归档）、情景记忆（流水账日记）、语义记忆（知识规律 + 向量检索）、用户偏好（key-value + 置信度）、Skill 记忆（SOP 三层按需加载）
- **VitePress 风格阅读器** — 左侧目录 + 右侧 Markdown 内容，基于 md-editor-v3 渲染，Shiki 代码高亮
- **游客访问** — 浏览器指纹登录，无需注册；支持后续升级为邮箱账号
- **Docker Compose 一键启动**

---

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3、TypeScript、Vite、md-editor-v3 |
| 后端 | Python 3.12、FastAPI、LangGraph、LlamaIndex |
| Agent 推理 | LangGraph（有向图编排）、PydanticAI |
| 任务队列 | Celery + Redis |
| 数据库 | PostgreSQL 16 + pgvector |
| 爬虫 | Playwright（无头 Chromium） |
| 部署 | Docker Compose |

---

## 设计文档

各模块的详细设计说明、架构决策和变更记录见 [docs/](./docs/README.md)。

## 快速开始

**前置条件：** 已安装 Docker 和 Docker Compose

```bash
git clone https://github.com/SkyingCooper/lore-seeker.git
cd lore-seeker

# 复制并填写 API Key
cp .env.example .env

# 编辑非敏感配置（模型、搜索提供商等）
vim backend/config.toml

# 启动所有服务
docker compose up --build
```

访问 `http://localhost:5173`。

---

## 配置说明

配置分为两个文件，职责分离：

**`backend/config.toml`** — 非敏感配置，可以提交到 git：
```toml
[llm]
default_provider = "deepseek"   # deepseek | gemini | openai

[llm.deepseek]
model = "deepseek-chat"
base_url = "https://api.deepseek.com"

[search]
api_provider = "tavily"         # tavily | serpapi | bing

[embedding]
provider = "dashscope"          # dashscope | openai | jina

[reranker]
provider = "dashscope"

[crawler]
enabled = true
headless = true
```

**`.env`** — 仅存放 secrets，不要提交：
```
DEEPSEEK_API_KEY=sk-...
DASHSCOPE_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
SECRET_KEY=你的随机密钥
```

环境变量优先级高于 `config.toml`，Docker 部署时可直接通过环境变量覆盖任意配置，无需修改文件。

---

## 项目结构

```
lore-seeker/
├── backend/
│   ├── agents/
│   │   ├── graph.py        # LangGraph 编排图（有向图 + 条件边）
│   │   ├── planner.py      # P&E 推理：任务拆解 + 质检评分
│   │   ├── searcher.py     # 搜索 API + Playwright 爬虫
│   │   ├── organizer.py    # Markdown 生成 + TOC 提取
│   │   └── retriever.py    # 向量检索 + 重排序 + 问答
│   ├── api/v1/             # FastAPI 路由（auth/users/search/reports/knowledge）
│   ├── core/
│   │   ├── config.py       # 配置加载（TOML source + .env）
│   │   ├── llm_router.py   # 多厂商 LLM 工厂
│   │   └── embedding_router.py  # 向量 + 重排序工厂
│   ├── db/models.py        # User / Topic / SearchTask / Report / KnowledgeChunk
│   │                       # + WorkingSession / EpisodicLog / SemanticMemory
│   │                       # + UserPreference / SkillMemory（五类记忆）
│   ├── services/
│   │   ├── search_service.py    # API 搜索 + 爬虫
│   │   └── knowledge_service.py # Markdown 切片 + 向量入库
│   ├── worker/tasks.py     # Celery 异步任务（驱动 Agent 图）
│   └── config.toml         # 非敏感配置
├── frontend/
│   └── src/
│       ├── views/          # Login / Browse / Report / Reports / Settings
│       └── layouts/        # 主侧边栏布局
└── docker-compose.yml      # db / redis / backend / worker / frontend
```

---

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/auth/guest` | 游客登录（浏览器指纹） |
| POST | `/api/v1/auth/register` | 邮箱注册 |
| POST | `/api/v1/auth/login` | 登录 |
| GET | `/api/v1/search/topics` | 获取主题列表 |
| POST | `/api/v1/search/topics` | 创建主题 |
| POST | `/api/v1/search/start` | 启动搜索任务（异步） |
| GET | `/api/v1/search/tasks/{id}` | 查询任务状态 |
| GET | `/api/v1/reports/` | 获取报告列表 |
| GET | `/api/v1/reports/{id}` | 获取报告完整 Markdown |
| POST | `/api/v1/knowledge/query` | 语义检索 + 问答 |

交互式接口文档：`http://localhost:8000/docs`

---

## License

本项目基于 **MIT + Commons Clause** 授权。

- 允许：个人使用、学习研究、学术用途、开源项目、非商业内部工具
- 需要授权：任何商业用途（含 SaaS 部署、付费服务、以本项目功能为核心的商业产品）

商业授权请联系：[github.com/SkyingCooper](https://github.com/SkyingCooper)

详见 [LICENSE](./LICENSE)。
