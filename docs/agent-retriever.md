# 检索 Agent (Retriever)

## 职责

响应用户的自然语言提问，通过向量检索 + 重排序找到最相关的知识片段，生成有来源依据的回答。

## 检索流程

```
用户问题
    │
    ▼
向量化（embedding_router）
    │
    ▼
pgvector 余弦相似度检索 → Top-20 候选 chunks
    │
    ▼
重排序模型（reranker）精排 → Top-5
    │
    ▼
LLM 基于上下文生成回答
    │
    ▼
返回：{ answer, sources: [{content, report_id, score}] }
```

## 向量检索

使用 pgvector 的 `<=>` 余弦距离算子：

```sql
SELECT id, content, report_id, metadata,
       1 - (embedding <=> :vec::vector) AS score
FROM knowledge_chunks
ORDER BY embedding <=> :vec::vector
LIMIT 20
```

召回 Top-20 是为了给重排序模型足够的候选集，最终只取 Top-5 送入 LLM。

**当前限制**：检索范围是全库（所有用户的 chunks）。后续需增加 `user_id` 过滤，确保用户只检索自己的知识库。

## 重排序

调用 `embedding_router.rerank(query, documents)`，返回按相关性重新排序的结果列表，每项包含 `index`、`score`、`text`。

重排序模型比向量相似度更精准，能理解语义而非仅匹配向量距离。

## 问答生成

**System prompt**：要求 LLM 基于提供的上下文回答，上下文不足时明确说明，不编造。

**Context 构建**：将 Top-5 chunks 拼接为编号列表，格式：
```
[1] chunk内容
[2] chunk内容
...
```

**Prompt 策略**：temperature=0.3，保持回答准确性的同时允许适度表达

## 相关文件

- `backend/agents/retriever.py` — 检索 + 问答实现
- `backend/api/v1/knowledge.py` — `/query` 接口
- `backend/core/embedding_router.py` — 向量化 + 重排序路由

---

## 2025-05-27 — 初始设计

**背景**：需要支持用户对已入库知识进行自然语言问答。

**决策**：采用"向量召回 → 重排序精排 → LLM 生成"的标准 RAG 流程，召回 Top-20 再精排到 Top-5，平衡召回率和精度。

**待解决**：
- 检索未做用户隔离，需在 SQL 中加 `user_id` 过滤
- 未实现多轮对话上下文，每次问答独立

**影响范围**：`agents/retriever.py`、`api/v1/knowledge.py`
