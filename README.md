# Lore Seeker

> An AI-native multi-agent knowledge system  
> Built for Deep Research, Knowledge Persistence, Intelligent Retrieval, and Long-Term Memory

---

# 1. Introduction

Lore Seeker is:

# “A Multi-Agent Driven Knowledge Operating System (Knowledge OS)”

The system orchestrates multiple agents to perform:

```text
Search → Clean → Organize → Structure → Store → Retrieve → Long-Term Memory
```

Ultimately forming a knowledge system that is:

- Searchable
- Traceable
- Extensible
- Persistent
- Continuously Evolvable

---

# 2. Project Goals

This project is not a traditional chatbot.

Its core objective is to build an:

# AI-Native Knowledge Infrastructure

---

## 1. Deep Research

Automatically:

- Search
- Read
- Summarize
- Cluster
- Generate structured knowledge systems

---

## 2. Knowledge Persistence

Transform temporary search results into:

```text
Long-term knowledge assets
```

---

## 3. AI-Native Knowledge Base

Build:

- Knowledge Trees
- TOC (Table of Contents)
- Citation Tracing
- Long-Term Memory
- Hybrid Retrieval

---

## 4. Multi-Agent Collaboration

Through:

- Planner Agent
- Search Agent
- Organize Agent
- Retrieval Agent
- Evaluation Agent

to automate complex knowledge workflows.

---

# 3. System Architecture

Overall architecture:

```text
                ┌────────────┐
                │    User    │
                └─────┬──────┘
                      │
              ┌───────▼────────┐
              │ Planner Agent  │
              └───────┬────────┘
                      │
      ┌───────────────┼────────────────┐
      │               │                │
      ▼               ▼                ▼
Search Agent   Organize Agent   Retrieval Agent
      │
      ▼
Knowledge Processing Pipeline
      │
      ▼
 PostgreSQL + pgvector
```

---

# 4. Core Agent Design

## 1. Planner Agent

Responsible for:

- User intent analysis
- Task decomposition
- Workflow planning
- Agent orchestration
- Quality evaluation
- Personalized memory

---

## 2. Search Agent

Responsible for:

- Website searching
- Web crawling
- Content extraction
- Information normalization
- Source credibility analysis

---

## 3. Organize Agent

Responsible for:

- Deduplication
- Clustering
- Knowledge organization
- TOC generation
- Markdown document generation
- Knowledge tree construction

---

## 4. Retrieval Agent

Responsible for:

- Query Rewrite
- Hybrid Search
- Reranking
- Context Compression
- RAG responses

---

## 5. Evaluation Agent

Responsible for:

- Hallucination detection
- Citation validation
- Structural completeness evaluation
- Quality scoring

---

# 5. Technology Stack

## Backend

| Technology | Purpose |
|---|---|
| Python | Primary programming language |
| FastAPI | API framework |
| LangGraph | Multi-agent workflows |
| LlamaIndex | RAG / Retrieval |
| PydanticAI | Agent schema system |
| Celery | Async task processing |
| Redis | Cache / Queue |
| PostgreSQL | Primary database |
| pgvector | Vector retrieval |

---

## Frontend

| Technology | Purpose |
|---|---|
| Vue3 | Frontend framework |
| TypeScript | Type system |
| Pinia | State management |
| Vite | Build tool |
| md-editor-v3 | Markdown rendering |

---

## AI / Retrieval

| Technology | Purpose |
|---|---|
| OpenAI | LLM provider |
| Anthropic | Claude models |
| Gemini | Multi-model support |
| BGE Reranker | Reranking |
| Jina Embedding | Embeddings |

---

# 6. Core Features

## 1. Web-Scale Knowledge Search

Supports:

- Targeted websites
- Multiple search sources
- Deep crawling
- Content extraction

---

## 2. Automatic Knowledge Organization

Automatically generates:

- TOC
- Knowledge Trees
- Markdown Documents
- References
- FAQs

---

## 3. Hybrid Retrieval

Supports:

- BM25
- Vector Search
- Hybrid Search
- Reranking
- Context Compression

---

## 4. Long-Term Knowledge Persistence

Supports:

- Vector storage
- Document storage
- Chunk management
- Persistent memory

---

## 5. Citation Tracing

All knowledge supports:

```text
Source tracing
```

Ensuring:

- Verifiability
- Traceability
- Reduced hallucinations

---

# 7. Project Structure

Core structure:

```text
lore-seeker/
├── apps/
├── packages/
├── frontend/
├── infrastructure/
├── context/
├── tests/
└── docs/
```

---

# 8. Context Engineering System

This project introduces a dedicated:

# Context Engineering System

Designed for:

- Claude Code
- Cursor
- Gemini CLI
- AI Agent IDEs

to maintain long-term engineering context.

---

## context Directory Structure

```text
context/
├── architecture/
├── decisions/
├── prompts/
├── workflows/
├── agents/
├── conventions/
├── experiments/
└── roadmap/
```

---

## Goal

Enable:

# “Shared Long-Term Engineering Memory Between Humans and AI”

Including:

- Architecture decisions
- Prompt evolution
- Workflow design
- Experiment records
- Incident postmortems

---

# 9. Why LangGraph

Because this project is fundamentally:

```text
State Machines + Workflows + Agent DAGs
```

rather than a simple chatbot.

LangGraph provides:

- StateGraph
- DAG workflows
- Retry mechanisms
- Conditional routing
- Human-in-the-loop support

making it ideal for complex multi-agent systems.

---

# 10. RAG Design

The project uses a:

# Multi-Stage Retrieval Pipeline

```text
Query Rewrite
    ↓
Hybrid Search
    ↓
Rerank
    ↓
Context Compression
    ↓
LLM Response
```

---

# 11. Knowledge Storage Design

The system uses:

## PostgreSQL + pgvector

to store:

- Documents
- Chunks
- Embeddings
- Citations
- User memory

---

# 12. Workflow Design

Current workflows include:

| Workflow | Purpose |
|---|---|
| knowledge_build | Build structured knowledge systems |
| rag_chat | RAG-based QA |
| deep_research | Deep research workflows |

---

# 13. Running the Project

## 1. Initialize the Project

```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

---

## 2. Start Backend

```bash
uvicorn apps.api.main:app --reload
```

---

## 3. Start Worker

```bash
celery -A apps.worker.celery_app worker --loglevel=info
```

---

## 4. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

---

# 14. Future Roadmap

## V1

- Basic multi-agent system
- Search + Organization
- Hybrid Retrieval
- Markdown Knowledge Base

---

## V2

- Knowledge Graph
- Agent Memory
- Deep Research
- Multimodal Support

---

## V3

- Autonomous Agents
- Browser Agents
- MCP Integration
- Multi-user Collaboration

---

# 15. Design Principles

## 1. Workflow First

Workflow > Agent Chat

---

## 2. Context Engineering

Context Engineering > Prompt Engineering

---

## 3. Structured Output

Structured Output > Free-form Text

---

## 4. Knowledge Persistence

Long-term knowledge persistence > One-time responses

---

## 5. Citation Required

All knowledge must be traceable.

---

# 16. Use Cases

Suitable for:

- AI Knowledge Bases
- Deep Research Systems
- Enterprise Knowledge Platforms
- Technical Documentation Systems
- NotebookLM-like products
- Perplexity-like products
- AI Search Systems

---

# 17. Project Status

Current phase:

```text
Architecture Design / MVP Development
```

---

# 18. License

Lore Seeker Community License 1.0

- Personal Use: Allowed
- Research Use: Allowed
- Educational Use: Allowed
- Commercial Use: Prohibited without permission

---

# 19. Acknowledgements

Special thanks to:

- LangGraph
- LlamaIndex
- FastAPI
- PostgreSQL
- pgvector
- OpenAI
- Anthropic

and the broader open-source AI ecosystem.