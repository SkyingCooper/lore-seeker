"""知识入库服务：Markdown 按 TOC 层级切片 + 向量化 + 存储。"""
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Report, KnowledgeChunk, SearchTask
from core.embedding_router import get_embeddings
from datetime import datetime


async def store_report(
    db: AsyncSession,
    task: SearchTask,
    content_md: str,
    toc: list,
    summary: str | None = None,
    result_count: int = 0,
) -> Report:
    report = Report(
        topic_id=task.topic_id,
        task_id=task.id,
        status="completed",
        content_md=content_md,
        toc=toc,
        summary=summary,
        result_count=result_count,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.add(report)
    await db.flush()

    chunks = _split_hierarchical(content_md, toc)
    if chunks:
        for chunk in chunks:
            chunk["summary"] = _summarize_chunk(chunk["content"])

        summaries = [c["summary"] for c in chunks]
        embeddings = await get_embeddings(summaries)
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            db.add(KnowledgeChunk(
                report_id=report.id,
                chunk_index=i,
                section_title=chunk["section_title"],
                section_level=chunk["section_level"],
                section_anchor=chunk["section_anchor"],
                parent_title=chunk.get("parent_title"),
                content=chunk["content"],
                summary=chunk["summary"],
                embedding=vec,
            ))

    task.status = "completed"
    await db.commit()
    return report


def _split_hierarchical(md: str, toc: list, chunk_size: int = 800, overlap: int = 100) -> list[dict]:
    """按 Markdown 标题分层切片，关联 TOC 中的层级关系。"""
    import re

    # 构建 TOC 查找表：anchor → {title, level}
    toc_map = {}
    parent_map = {}
    stack: list[dict] = []  # 维护层级栈，确定父子关系

    for entry in toc:
        anchor = entry.get("anchor", "")
        level = entry.get("level", 1)
        title = entry.get("title", "")
        toc_map[anchor] = entry

        # 弹出所有 >= 当前 level 的栈元素，栈顶即为父级
        while stack and stack[-1]["level"] >= level:
            stack.pop()
        parent_title = stack[-1]["title"] if stack else None
        parent_map[anchor] = parent_title
        stack.append({"level": level, "title": title, "anchor": anchor})

    # 按所有标题分割
    sections = re.split(r"\n(?=#{1,3} )", md)
    chunks: list[dict] = []
    current_section = {"title": "", "level": 0, "anchor": "", "parent": None}

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # 提取标题
        heading_match = re.match(r"^(#{1,3})\s+(.+?)(?:\s*\{#([^}]+)\})?\s*$", section.split("\n")[0])
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            anchor = heading_match.group(3) or _slugify(title)
            current_section = {
                "title": title,
                "level": level,
                "anchor": anchor,
                "parent": parent_map.get(anchor),
            }

        # 切片
        body = section
        if len(body) <= chunk_size:
            chunks.append({
                "content": body,
                "section_title": current_section["title"],
                "section_level": current_section["level"],
                "section_anchor": current_section["anchor"],
                "parent_title": current_section["parent"],
            })
        else:
            for start in range(0, len(body), chunk_size - overlap):
                piece = body[start: start + chunk_size].strip()
                if piece:
                    chunks.append({
                        "content": piece,
                        "section_title": current_section["title"],
                        "section_level": current_section["level"],
                        "section_anchor": current_section["anchor"],
                        "parent_title": current_section["parent"],
                    })

    return chunks


def _summarize_chunk(content: str, min_len: int = 50, max_len: int = 150) -> str:
    """生成用于检索预览和 embedding 的轻量摘要。"""
    import re

    text = re.sub(r"```.*?```", " ", content, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)]\([^)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"[-*_]{2,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return content[:max_len].strip()
    if len(text) <= max_len:
        return text

    summary = text[:max_len].strip()
    sentence_end = max(summary.rfind("。"), summary.rfind("."), summary.rfind("！"), summary.rfind("？"))
    if sentence_end >= min_len:
        return summary[: sentence_end + 1].strip()
    return summary


def _slugify(text: str) -> str:
    """简单中文兼容的 anchor 生成。"""
    return text.lower().replace(" ", "-").replace("/", "-")
