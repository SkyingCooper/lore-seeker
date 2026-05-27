# Lore Seeker

> A multi-agent knowledge base system that automatically searches, organizes, and retrieves knowledge from the web.

[中文文档](./README_zh.md)

## Overview

Lore Seeker is a LangGraph-orchestrated multi-agent system. The core idea: **let AI handle the full chain of "read the web → distill knowledge → build a structured knowledge base"**, and persist the result into a continuously searchable personal library.

Give it a topic. It searches, filters, organizes, and stores — producing a Markdown knowledge document with a table of contents, ready for natural language Q&A.

---

## Architecture

### Agent Pipeline

```
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Planner Agent                               │
│  P&E Reasoning:  Perception → parse intent, decompose queries,    │
│                              predict knowledge structure           │
│                  Evaluation → quality scoring, feedback-driven     │
│                              retry, user preference learning       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ search plan (sub-queries + expected chapters)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Searcher Agent                              │
│  API mode:     Tavily / SerpAPI / Bing, with domain filtering     │
│  Crawler mode: Playwright headless browser, full-page extraction  │
│  Hybrid mode:  API first, crawler fills in depth                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ raw results (title + url + content)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Organizer Agent                             │
│  Filters low-quality content, clusters by relevance               │
│  Generates structured Markdown with YAML front matter + TOC       │
└────────────────────────────┬─────────────────────────────────────┘
                             │ Markdown document + TOC
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                Quality Check (Planner · Evaluation)               │
│  Scores the document (0–100); score ≥ 75 passes                   │
│  On failure: injects feedback into Organizer, retries up to 3×    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ pass
                             ▼
                      Three-layer storage (see below)
```

### Planner Agent — P&E Reasoning

The Planner is the system's brain, operating in two distinct reasoning phases:

**Perception (plan)**
- Parses user intent, resolves ambiguous phrasing
- Decomposes a single query into multiple sub-queries covering different dimensions of the topic
- Predicts the expected knowledge structure (chapter titles) to constrain the Organizer
- Incorporates the user's historical preferences (`preferences` field) to adjust search strategy

**Evaluation (judge)**
- Scores the Organizer's Markdown output across multiple dimensions: completeness, structure clarity, factual accuracy
- Produces specific, actionable feedback injected into the next generation round
- Records quality scores per task, gradually building a user preference model

```
Perception                          Evaluation
──────────────────────────          ──────────────────────────
user intent → sub-query list        Markdown → quality score
history prefs → strategy adjust     score feedback → retry prompt
expected structure → chapter hints  pass record → preference update
```

### Three-Layer Storage

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Relational (PostgreSQL)                             │
│  Structured metadata: users, topics, tasks, reports           │
│  Supports filtering by time, quality score, topic, etc.       │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Vector (pgvector)                                   │
│  Markdown split into chunks by heading, each chunk embedded   │
│  Cosine similarity retrieval + reranker model for Top-K       │
│  Dimension configurable (DashScope text-embedding-v3: 1536)   │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Cache / Queue (Redis)                               │
│  Celery task queue: async Agent pipeline, non-blocking API    │
│  Task state cache: frontend polls for progress                │
└─────────────────────────────────────────────────────────────┘
```

Retrieval flow across all three layers:
1. User question → vector layer recalls Top-20 candidate chunks
2. Reranker model re-scores → keep Top-5
3. Relational layer enriches with report metadata (title, source, date)
4. LLM generates the final answer from context

---

## Features

- **P&E dual-phase planning** — Perception decomposes tasks, Evaluation closes the quality loop with up to 3 automatic refinement rounds
- **Multi-agent pipeline** — Planner, Searcher, Organizer, Retriever each own a single responsibility; orchestrated as a LangGraph directed graph
- **Flexible LLM routing** — DeepSeek, Gemini, OpenAI; one-line switch in `config.toml`
- **Dual search modes** — Search API (Tavily / SerpAPI / Bing) and Playwright crawler, mixable, with per-topic site targeting
- **Three-layer storage** — Relational + vector + cache, covering structured queries and semantic retrieval
- **Configurable embedding & reranking** — Alibaba Cloud DashScope, OpenAI, Jina; provider-swappable via config
- **Personalized memory** — Planner Agent records user editing habits and builds a preference model over time
- **VitePress-style reader** — Left TOC + right Markdown, rendered with md-editor-v3, Shiki code highlighting
- **Guest access** — Browser fingerprint login, no registration required; upgradeable to email account
- **Docker Compose** — One command to start everything

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3, TypeScript, Vite, md-editor-v3 |
| Backend | Python 3.12, FastAPI, LangGraph, LlamaIndex |
| Agent Reasoning | LangGraph (directed graph), PydanticAI |
| Task Queue | Celery + Redis |
| Database | PostgreSQL 16 + pgvector |
| Crawler | Playwright (headless Chromium) |
| Deployment | Docker Compose |

---

## Design Docs

Detailed design specs, architecture decisions, and change history for each module: [docs/](./docs/README.md).

## Quick Start

**Prerequisites:** Docker and Docker Compose

```bash
git clone https://github.com/SkyingCooper/lore-seeker.git
cd lore-seeker

# Copy and fill in your API keys
cp .env.example .env

# Edit non-sensitive config (models, search provider, etc.)
vim backend/config.toml

# Start all services
docker compose up --build
```

Open `http://localhost:5173`.

---

## Configuration

Configuration is split into two files:

**`backend/config.toml`** — non-sensitive settings, safe to commit:
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

**`.env`** — secrets only, never commit:
```
DEEPSEEK_API_KEY=sk-...
DASHSCOPE_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
SECRET_KEY=your-random-secret
```

Environment variables take precedence over `config.toml`, so Docker deployments can override any value without modifying files.

---

## Project Structure

```
lore-seeker/
├── backend/
│   ├── agents/
│   │   ├── graph.py        # LangGraph directed graph + conditional edges
│   │   ├── planner.py      # P&E reasoning: task decomposition + quality check
│   │   ├── searcher.py     # Search API + Playwright crawler
│   │   ├── organizer.py    # Markdown generation + TOC extraction
│   │   └── retriever.py    # Vector search + reranking + QA
│   ├── api/v1/             # FastAPI routes (auth/users/search/reports/knowledge)
│   ├── core/
│   │   ├── config.py       # Settings loader (TOML source + .env)
│   │   ├── llm_router.py   # Multi-provider LLM factory
│   │   └── embedding_router.py  # Embedding + reranker factory
│   ├── db/models.py        # User / Topic / SearchTask / Report / KnowledgeChunk
│   ├── services/
│   │   ├── search_service.py    # API search + crawler
│   │   └── knowledge_service.py # Markdown chunking + vector ingestion
│   ├── worker/tasks.py     # Celery async tasks (drives the Agent graph)
│   └── config.toml         # Non-sensitive configuration
├── frontend/
│   └── src/
│       ├── views/          # Login / Browse / Report / Reports / Settings
│       └── layouts/        # Main sidebar layout
└── docker-compose.yml      # db / redis / backend / worker / frontend
```

---

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/guest` | Guest login via browser fingerprint |
| POST | `/api/v1/auth/register` | Register with email + password |
| POST | `/api/v1/auth/login` | Login |
| GET | `/api/v1/search/topics` | List saved topics |
| POST | `/api/v1/search/topics` | Create a topic |
| POST | `/api/v1/search/start` | Start a search task (async) |
| GET | `/api/v1/search/tasks/{id}` | Poll task status |
| GET | `/api/v1/reports/` | List all reports |
| GET | `/api/v1/reports/{id}` | Get report with full Markdown |
| POST | `/api/v1/knowledge/query` | Semantic search + QA |

Interactive docs available at `http://localhost:8000/docs`.

---

## License

This project is licensed under **MIT + Commons Clause**.

- Permitted: personal use, research, study, academic work, open-source projects, internal non-commercial tools
- Requires authorization: any commercial use, including SaaS deployment, paid services, or products whose value derives from this Software

To request a commercial license, contact: [github.com/SkyingCooper](https://github.com/SkyingCooper)

See [LICENSE](./LICENSE) for the full terms.
