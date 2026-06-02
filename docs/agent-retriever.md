# Retriever Agent 设计

## 1. 模块职责

Retriever 负责对已入库知识进行语义检索，并基于检索结果生成有来源的回答。

对应代码：

- `backend/agents/retriever.py`
- `backend/api/v1/knowledge.py`
- `backend/core/embedding_router.py`

## 2. RAG 流程

### 背景

用户需要围绕自己的报告和知识库提问，回答必须基于已入库内容，不能跨用户泄露数据。

### 决策

采用“向量召回 → 重排序 → LLM 回答”的 RAG 流程，并在 SQL 层按 `user_id` 隔离。

### 实现要点

流程：

```text
用户问题
  -> embedding_router 生成 query 向量
  -> pgvector 召回 Top-N chunks
  -> reranker 精排
  -> LLM 基于 Top-5 chunks 回答
  -> 返回 answer + sources
```

隔离查询路径：

```text
knowledge_chunks.report_id
  -> reports.task_id
  -> search_tasks.user_id
  -> current_user.id
```

SQL 必须包含：

```sql
JOIN reports r ON r.id = kc.report_id
JOIN search_tasks st ON st.id = r.task_id
WHERE st.user_id = :user_id
  AND st.deleted_at IS NULL
```

详细工作流程：

1. API 层接收用户自然语言问题。
2. `knowledge.py` 通过 `require_member` 获取当前用户。
3. 调用 `retrieve(query, db, user_id, top_k)`。
4. Retriever 调用 `embedding_router` 生成查询向量。
5. 使用 pgvector 从 `knowledge_chunks` 召回候选切片。
6. SQL 通过 `reports` 和 `search_tasks` 关联过滤 `user_id`。
7. 召回结果放大为 `top_k * 4`，给 reranker 留出候选空间。
8. 将候选切片正文传给 reranker 精排。
9. 取前 5 条切片拼接为 LLM 上下文。
10. LLM 只基于上下文生成回答。
11. 返回 `answer` 和 `sources`。
12. `sources` 包含切片内容摘要、`report_id` 和相关性分数。

### 验收标准

- 用户只能检索自己任务生成的知识切片。
- 游客不能调用 `/api/v1/knowledge/query`。
- 返回结果包含答案和来源。

## 3. 向量召回

### 背景

向量召回用于从大量切片中快速找到语义接近的候选。

### 决策

使用 pgvector 余弦距离算子 `<=>` 召回候选切片。

### 实现要点

- `top_k` 默认按前端请求放大为 `top_k * 4`。
- 检索字段为 `KnowledgeChunk.embedding`。
- 召回结果包含 `id`、`content`、`report_id`、`score`。

SQL 形态：

```sql
SELECT kc.id,
       kc.content,
       kc.report_id,
       1 - (kc.embedding <=> :query_embedding) AS score
FROM knowledge_chunks kc
JOIN reports r ON r.id = kc.report_id
JOIN search_tasks st ON st.id = r.task_id
WHERE st.user_id = :user_id
  AND st.deleted_at IS NULL
ORDER BY kc.embedding <=> :query_embedding
LIMIT :limit
```

### 验收标准

- 查询向量生成失败时接口返回错误。
- 无命中时返回空来源，并由回答逻辑说明上下文不足。

## 4. 重排序与回答

### 背景

向量距离只能粗召回，最终回答需要更精确的上下文排序。

### 决策

召回结果交给 reranker 精排，取前 5 条进入 LLM 上下文。

### 实现要点

- `embedding_router.rerank(query, documents)` 返回排序后的 index 和 score。
- LLM prompt 明确要求只基于上下文回答。
- sources 返回每条切片前 200 字、`report_id` 和 rerank score。

### 验收标准

- 回答不得编造上下文外事实。
- sources 顺序与最终使用上下文一致。
- rerank score 能回传给前端用于展示。

## 5. 相关文件

- `backend/agents/retriever.py`：检索、重排序和回答生成。
- `backend/api/v1/knowledge.py`：知识查询 API 和用户权限入口。
- `backend/core/embedding_router.py`：embedding 与 rerank provider 路由。
