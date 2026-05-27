from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from api.v1.auth import get_current_user
from db.models import User, Report, SearchTask

router = APIRouter()


@router.get("/")
async def list_reports(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Report, SearchTask)
        .join(SearchTask, Report.task_id == SearchTask.id)
        .where(SearchTask.user_id == current_user.id)
        .order_by(Report.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "summary": r.summary,
            "toc": r.toc,
            "created_at": r.created_at.isoformat(),
            "quality_score": t.quality_score,
        }
        for r, t in rows
    ]


@router.get("/{report_id}")
async def get_report(report_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    task = await db.get(SearchTask, report.task_id)
    if task.user_id != current_user.id:
        raise HTTPException(403, "Forbidden")
    return {
        "id": str(report.id),
        "title": report.title,
        "content_md": report.content_md,
        "toc": report.toc,
        "summary": report.summary,
        "created_at": report.created_at.isoformat(),
    }
