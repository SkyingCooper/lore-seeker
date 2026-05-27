"""整理 Agent：过滤、编排、生成 Markdown 知识体系 + TOC。"""
import json
from agents.graph import AgentState
from core.llm_router import get_llm
from langchain_core.messages import HumanMessage, SystemMessage

_ORGANIZE_SYSTEM = """你是一个专业的知识整理专家。
根据提供的搜索结果，生成一份结构化的 Markdown 知识文档。

要求：
1. 按相关性组织成若干章节（## 二级标题），每章若干节（### 三级标题）
2. 内容准确、去重、有逻辑性
3. 代码示例使用代码块
4. 在文档最开头输出 YAML front matter，包含 title 和 toc（章节列表）
5. 如果有质检反馈，请根据反馈改进

输出格式：
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
"""


async def organizer_node(state: AgentState) -> dict:
    raw = state.get("raw_results", [])
    feedback = state.get("quality_feedback", "")

    # 截取前 20 条，避免超 token
    snippets = "\n\n".join(
        f"[{i+1}] {r.get('title','')}\n{r.get('url','')}\n{r.get('content','')[:500]}"
        for i, r in enumerate(raw[:20])
    )

    user_msg = f"查询主题：{state['query']}\n\n搜索结果：\n{snippets}"
    if feedback:
        user_msg += f"\n\n质检反馈（请改进）：{feedback}"

    llm = get_llm(temperature=0.4)
    messages = [
        SystemMessage(content=_ORGANIZE_SYSTEM),
        HumanMessage(content=user_msg),
    ]
    resp = await llm.ainvoke(messages)
    md = resp.content

    toc = _extract_toc(md)
    return {"organized_md": md, "toc": toc}


def _extract_toc(md: str) -> list:
    """从 YAML front matter 或标题行提取 TOC。"""
    import re
    import yaml

    fm_match = re.match(r"^---\n(.*?)\n---", md, re.DOTALL)
    if fm_match:
        try:
            data = yaml.safe_load(fm_match.group(1))
            if isinstance(data, dict) and "toc" in data:
                return data["toc"]
        except Exception:
            pass

    # fallback：从标题行生成
    toc = []
    for line in md.splitlines():
        m = re.match(r"^(#{2,3})\s+(.+)", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = re.sub(r"[^\w一-鿿-]", "", title.lower().replace(" ", "-"))
            toc.append({"level": level, "title": title, "anchor": anchor})
    return toc
