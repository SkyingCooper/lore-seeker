```bash
#!/usr/bin/env bash

# =========================================================
# Lore Seeker Bootstrap Script
#
# 作用：
# 自动初始化 Lore Seeker 多 Agent 知识库系统
#
# 功能：
# 1. 创建完整项目目录结构
# 2. 自动生成基础文件
# 3. 自动写入文件头注释
# 4. 初始化 context 工程上下文系统
# 5. 初始化 ADR / Prompt / Workflow 文档体系
# 6. 初始化前后端工程结构
#
# 适用于：
# - Claude Code
# - Cursor
# - Gemini CLI
# - OpenAI Agents
# - LangGraph
#
# =========================================================

set -e

PROJECT_NAME="lore-seeker"

echo "🚀 Initializing project: ${PROJECT_NAME}"

mkdir -p ${PROJECT_NAME}
cd ${PROJECT_NAME}

# =========================================================
# Common Helpers
# =========================================================

create_py() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
# $(basename "$1") - $2

EOF
}

create_ts() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
// $(basename "$1") - $2

EOF
}

create_vue() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
<!-- $(basename "$1") - $2 -->

<template>
  <div></div>
</template>

<script setup lang="ts">
</script>

<style scoped>
</style>
EOF
}

create_md() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
# $(basename "$1")

EOF
}

create_yaml() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
# $(basename "$1") - $2

EOF
}

create_json() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
{}
EOF
}

create_sh() {
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
#!/usr/bin/env bash
# $(basename "$1") - $2

EOF

  chmod +x "$1"
}

create_gitkeep() {
  mkdir -p "$1"
  touch "$1/.gitkeep"
}

# =========================================================
# Root Structure
# =========================================================

mkdir -p \
  apps \
  packages \
  frontend \
  infrastructure \
  scripts \
  tests \
  docs \
  context

# =========================================================
# apps/api
# =========================================================

create_py apps/api/main.py "FastAPI application entrypoint"
create_py apps/api/lifespan.py "Application lifecycle management"
create_py apps/api/dependencies.py "Dependency injection"

create_py apps/api/routes/chat.py "Chat API routes"
create_py apps/api/routes/knowledge.py "Knowledge API routes"
create_py apps/api/routes/search.py "Search API routes"
create_py apps/api/routes/retrieval.py "Retrieval API routes"
create_py apps/api/routes/memory.py "Memory API routes"
create_py apps/api/routes/health.py "Health check routes"

create_py apps/api/middleware/auth.py "Authentication middleware"
create_py apps/api/middleware/logging.py "Logging middleware"
create_py apps/api/middleware/tracing.py "Tracing middleware"
create_py apps/api/middleware/rate_limit.py "Rate limit middleware"

create_py apps/api/config/settings.py "Application settings"
create_py apps/api/config/logging.py "Logging configuration"

# =========================================================
# apps/worker
# =========================================================

create_py apps/worker/main.py "Worker entrypoint"
create_py apps/worker/celery_app.py "Celery app initialization"

create_py apps/worker/tasks/search_task.py "Search async task"
create_py apps/worker/tasks/organize_task.py "Organize async task"
create_py apps/worker/tasks/embedding_task.py "Embedding generation task"
create_py apps/worker/tasks/rerank_task.py "Rerank async task"
create_py apps/worker/tasks/cleanup_task.py "Cleanup async task"

# =========================================================
# packages/agents
# =========================================================

AGENTS=("planner" "search" "organize" "retrieval" "evaluation" "memory")

for agent in "${AGENTS[@]}"
do
  create_py packages/agents/${agent}/agent.py "${agent} agent implementation"
  create_py packages/agents/${agent}/prompt.py "${agent} prompts"
  create_py packages/agents/${agent}/schemas.py "${agent} schemas"
  create_py packages/agents/${agent}/memory.py "${agent} memory"
  create_py packages/agents/${agent}/policy.py "${agent} policy"
  create_md packages/agents/${agent}/README.md
done

# =========================================================
# packages/workflows
# =========================================================

WORKFLOWS=("knowledge_build" "rag_chat" "deep_research")

for workflow in "${WORKFLOWS[@]}"
do
  create_py packages/workflows/${workflow}/graph.py "${workflow} workflow graph"
  create_py packages/workflows/${workflow}/state.py "${workflow} workflow state"

  create_py packages/workflows/${workflow}/nodes/planner_node.py "Planner node"
  create_py packages/workflows/${workflow}/nodes/search_node.py "Search node"
  create_py packages/workflows/${workflow}/nodes/organize_node.py "Organize node"
  create_py packages/workflows/${workflow}/nodes/evaluate_node.py "Evaluation node"

  create_py packages/workflows/${workflow}/edges/routing.py "Workflow routing"

  create_py packages/workflows/${workflow}/policies/retry_policy.py "Retry policy"
  create_py packages/workflows/${workflow}/policies/timeout_policy.py "Timeout policy"

  create_md packages/workflows/${workflow}/README.md
done

# =========================================================
# packages/llm
# =========================================================

create_py packages/llm/base.py "Base LLM abstraction"
create_py packages/llm/factory.py "LLM factory"

LLMS=("openai" "anthropic" "gemini" "deepseek")

for provider in "${LLMS[@]}"
do
  create_py packages/llm/${provider}/client.py "${provider} client"
done

# =========================================================
# packages/retrieval
# =========================================================

create_py packages/retrieval/hybrid_search/bm25.py "BM25 search"
create_py packages/retrieval/hybrid_search/vector_search.py "Vector retrieval"
create_py packages/retrieval/hybrid_search/hybrid.py "Hybrid retrieval"

create_py packages/retrieval/reranker/bge.py "BGE reranker"
create_py packages/retrieval/reranker/jina.py "Jina reranker"

create_py packages/retrieval/query_rewrite/llm_rewrite.py "LLM query rewrite"

create_py packages/retrieval/chunking/semantic_chunk.py "Semantic chunking"
create_py packages/retrieval/chunking/markdown_chunk.py "Markdown chunking"

# =========================================================
# packages/knowledge
# =========================================================

create_py packages/knowledge/parser/html_parser.py "HTML parser"
create_py packages/knowledge/parser/pdf_parser.py "PDF parser"

create_py packages/knowledge/cleaner/html_cleaner.py "HTML cleaner"

create_py packages/knowledge/clustering/semantic_cluster.py "Semantic clustering"

create_py packages/knowledge/deduplication/exact_match.py "Exact deduplication"

create_py packages/knowledge/toc_generator/outline_builder.py "Outline builder"

create_py packages/knowledge/citation/citation_builder.py "Citation builder"

create_py packages/knowledge/summarizer/map_reduce.py "Map reduce summarizer"

# =========================================================
# packages/storage
# =========================================================

create_py packages/storage/postgres/client.py "PostgreSQL client"
create_py packages/storage/postgres/session.py "Database session"

create_py packages/storage/pgvector/vector_store.py "pgvector store"

create_py packages/storage/redis/client.py "Redis client"

create_py packages/storage/object_storage/minio.py "MinIO client"

# =========================================================
# packages/models
# =========================================================

create_py packages/models/document.py "Document models"
create_py packages/models/chunk.py "Chunk models"
create_py packages/models/citation.py "Citation models"
create_py packages/models/message.py "Message models"
create_py packages/models/memory.py "Memory models"

# =========================================================
# packages/observability
# =========================================================

create_py packages/observability/tracing/opentelemetry.py "OpenTelemetry tracing"

create_py packages/observability/logging/logger.py "Logging utilities"

create_py packages/observability/metrics/token_metrics.py "Token metrics"

# =========================================================
# packages/shared
# =========================================================

create_py packages/shared/config/settings.py "Shared settings"

create_py packages/shared/constants/constants.py "Global constants"

create_py packages/shared/exceptions/base.py "Base exceptions"

create_py packages/shared/utils/helpers.py "Helper utilities"

# =========================================================
# prompts
# =========================================================

create_gitkeep packages/prompts/planner
create_gitkeep packages/prompts/search
create_gitkeep packages/prompts/organize
create_gitkeep packages/prompts/retrieval
create_gitkeep packages/prompts/evaluation

# =========================================================
# frontend
# =========================================================

create_ts frontend/src/main.ts "Vue entrypoint"

create_vue frontend/src/App.vue "Root component"

create_vue frontend/src/pages/chat/index.vue "Chat page"
create_vue frontend/src/pages/knowledge/index.vue "Knowledge page"
create_vue frontend/src/pages/search/index.vue "Search page"

create_vue frontend/src/components/chat/ChatPanel.vue "Chat panel"

create_vue frontend/src/components/toc/TocSidebar.vue "TOC sidebar"

create_vue frontend/src/components/markdown/MarkdownViewer.vue "Markdown viewer"

create_vue frontend/src/components/citation/CitationPanel.vue "Citation panel"

create_ts frontend/src/router/index.ts "Vue router"

create_ts frontend/src/stores/chat.ts "Chat store"
create_ts frontend/src/stores/knowledge.ts "Knowledge store"

create_ts frontend/src/services/api.ts "Frontend API service"

# =========================================================
# infrastructure
# =========================================================

create_yaml infrastructure/compose/postgres.yml "PostgreSQL compose"
create_yaml infrastructure/compose/redis.yml "Redis compose"
create_yaml infrastructure/compose/minio.yml "MinIO compose"

# =========================================================
# scripts
# =========================================================

create_sh scripts/bootstrap.sh "Bootstrap script"
create_sh scripts/dev.sh "Development startup script"

# =========================================================
# tests
# =========================================================

create_gitkeep tests/unit
create_gitkeep tests/integration
create_gitkeep tests/e2e
create_gitkeep tests/evaluation

# =========================================================
# docs
# =========================================================

create_md docs/architecture/system_design.md
create_md docs/workflows/knowledge_build.md
create_md docs/database/schema.md
create_md docs/api/openapi.md

# =========================================================
# context
# =========================================================

# architecture
create_md context/architecture/system_overview.md
create_md context/architecture/agent_design.md
create_md context/architecture/workflow_design.md
create_md context/architecture/retrieval_design.md
create_md context/architecture/memory_design.md
create_md context/architecture/database_design.md

# ADR
create_md context/decisions/ADR-001-langgraph.md
create_md context/decisions/ADR-002-pgvector.md
create_md context/decisions/ADR-003-hybrid-search.md
create_md context/decisions/ADR-004-memory-system.md

# prompts
create_md context/prompts/planner_prompt_v1.md
create_md context/prompts/organize_prompt_v1.md
create_md context/prompts/retrieval_prompt_v1.md

# workflows
create_md context/workflows/knowledge_build.md
create_md context/workflows/rag_chat.md
create_md context/workflows/deep_research.md

# agents
create_md context/agents/planner_agent.md
create_md context/agents/search_agent.md
create_md context/agents/organize_agent.md
create_md context/agents/retrieval_agent.md
create_md context/agents/evaluation_agent.md

# conventions
create_md context/conventions/coding_style.md
create_md context/conventions/prompt_rules.md
create_md context/conventions/chunk_rules.md
create_md context/conventions/retrieval_rules.md
create_md context/conventions/naming_convention.md

# integrations
create_md context/integrations/openai.md
create_md context/integrations/anthropic.md
create_md context/integrations/jina.md
create_md context/integrations/firecrawl.md
create_md context/integrations/pgvector.md

# experiments
create_md context/experiments/rerank_test.md
create_md context/experiments/chunk_strategy.md
create_md context/experiments/embedding_comparison.md

# postmortems
create_md context/postmortems/retrieval_failure.md
create_md context/postmortems/hallucination_issue.md

# roadmap
create_md context/roadmap/v1.md
create_md context/roadmap/v2.md
create_md context/roadmap/future.md

# =========================================================
# Root Files
# =========================================================

create_md README.md
create_md README_CN.md

create_yaml docker-compose.yml "Docker compose configuration"

touch .env
touch .env.example
touch .gitignore

cat > Makefile <<EOF
# Makefile - Project commands

install:
\tpip install -r requirements.txt

run-api:
\tuvicorn apps.api.main:app --reload

run-worker:
\tcelery -A apps.worker.celery_app worker --loglevel=info

frontend:
\tcd frontend && npm run dev
EOF

cat > pyproject.toml <<EOF
# pyproject.toml - Python project configuration

[project]
name = "lore-seeker"
version = "0.1.0"
description = "Multi-agent knowledge system"

[tool.black]
line-length = 88

[tool.isort]
profile = "black"
EOF

echo ""
echo "✅ Lore Seeker project initialized successfully!"
echo ""
echo "📦 Includes:"
echo "   - Multi-agent architecture"
echo "   - LangGraph workflow system"
echo "   - Context engineering system"
echo "   - ADR architecture records"
echo "   - Prompt evolution management"
echo "   - Vue frontend scaffold"
echo "   - FastAPI backend scaffold"
echo "   - Retrieval infrastructure"
echo "   - Knowledge processing system"
echo ""
echo "🚀 Ready for development!"
```
