"""知识入库服务：Markdown 切片 + 向量化 + 存储。"""
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Report, KnowledgeChunk, SearchTask
from core.embedding_router import get_embeddings
from datetime import datetime


async def store_report(
    db: AsyncSession,
    task: SearchTask,
    title: str,
    content_md: str,
    toc: list,
    summary: str | None = None,
) -> Report:
    report = Report(
        task_id=task.id,
        title=title,
        content_md=content_md,
        toc=toc,
        summary=summary,
    )
    db.add(report)
    await db.flush()

    chunks = _split_markdown(content_md)
    if chunks:
        embeddings = await get_embeddings(chunks)
        for i, (chunk, vec) in enumerate(zip(chunks, embeddings)):
            db.add(KnowledgeChunk(
                report_id=report.id,
                chunk_index=i,
                content=chunk,
                embedding=vec,
            ))

    task.status = "done"
    task.finished_at = datetime.utcnow()
    await db.commit()
    return report


def _split_markdown(md: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """按段落切片，保持语义完整性。"""
    import re

    # 先按二级/三级标题分段
    sections = re.split(r"\n(?=#{2,3} )", md)
    chunks = []
    for section in sections:
        if len(section) <= chunk_size:
            if section.strip():
                chunks.append(section.strip())
        else:
            # 超长段落按字符滑窗切
            for start in range(0, len(section), chunk_size - overlap):
                piece = section[start: start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
    return chunks
