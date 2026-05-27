# 整理 Agent (Organizer)

## 职责

接收搜索原始结果，过滤低质量内容，按相关性聚类编排，生成结构化 Markdown 知识文档，并提取 TOC。

## Markdown 生成

**输入**：
- 原始搜索结果（最多取前 20 条，防止超 token）
- 规划 Agent 的预期章节列表（方向约束）
- 质检反馈（重试时注入）

**输出**：带 YAML front matter 的 Markdown 文档：

```markdown
---
title: 文档标题
toc:
  - level: 2
    title: 章节标题
    anchor: zhang-jie-biao-ti
  - level: 3
    title: 小节标题
    anchor: xiao-jie-biao-ti
---

# 文档标题

## 章节...
```

**Prompt 策略**：temperature=0.4，适度创造性以保证文档可读性

**质检反馈注入**：重试时在 user message 末尾追加 `质检反馈（请改进）：{feedback}`，Organizer 在生成时需针对性改进。

## TOC 提取

优先从 YAML front matter 解析 `toc` 字段；若解析失败，fallback 为扫描 `##` / `###` 标题行自动生成。

TOC 结构：
```python
[
  {"level": 2, "title": "章节标题", "anchor": "zhang-jie-biao-ti"},
  {"level": 3, "title": "小节标题", "anchor": "xiao-jie-biao-ti"},
]
```

`anchor` 生成规则：去除非字母数字和中文字符，空格转 `-`，全部小写。

## 切片策略

Markdown 入库前由 `knowledge_service.py` 切片：

1. 优先按 `##` / `###` 标题分段，保持语义完整性
2. 超过 800 字符的段落，使用滑窗切割（窗口 800，重叠 100）
3. 空段落跳过

**向量维度**：当前硬编码 1536（对应 DashScope `text-embedding-v3` 和 OpenAI `text-embedding-3-small`）。切换其他模型时需同步修改 `db/models.py` 中 `KnowledgeChunk.embedding` 的 `Vector(n)` 参数。

## 相关文件

- `backend/agents/organizer.py` — 节点实现（含 TOC 提取）
- `backend/services/knowledge_service.py` — 切片 + 向量入库

---

## 2025-05-27 — 初始设计

**背景**：需要将非结构化搜索结果转化为有层次的知识文档。

**决策**：要求 LLM 在输出中内嵌 YAML front matter，将 TOC 结构化数据和正文一起生成，避免二次解析正文提取目录。

**放弃的方案**：
- 先生成正文再单独提取 TOC：两次 LLM 调用，成本翻倍，且 TOC 与正文可能不一致
- 纯正则从标题行提取 TOC：无法获取 anchor，且中文标题处理复杂

**影响范围**：`agents/organizer.py`、`services/knowledge_service.py`、`db/models.py`
