from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.v1.auth import get_current_user, require_member
from db.models import Report, SearchTask, Topic, User

router = APIRouter()


class EvaluateRequest(BaseModel):
    satisfaction: str  # dissatisfied / neutral / satisfied
    notes: str | None = None


@router.get("/")
async def list_reports(
    task_id: int | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Report, Topic.title)
        .join(SearchTask, Report.task_id == SearchTask.id)
        .join(Topic, Report.topic_id == Topic.id)
        .where(
        SearchTask.user_id == current_user.id,
        SearchTask.deleted_at.is_(None),
        )
    )
    if task_id:
        stmt = stmt.where(Report.task_id == task_id)
    stmt = stmt.order_by(Report.created_at.desc())

    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "task_id": r.task_id,
            "topic_id": r.topic_id,
            "title": topic_title or f"Report #{r.id}",
            "status": r.status,
            "result_count": r.result_count,
            "quality_score": r.quality_score,
            "summary": r.summary,
            "user_satisfaction": r.user_satisfaction,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "execution_duration": r.execution_duration,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, topic_title in rows
    ]


@router.get("/{report_id}")
async def get_report(report_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    task = await db.get(SearchTask, report.task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(403, "Forbidden")
    topic = await db.get(Topic, report.topic_id)

    return {
        "id": report.id,
        "task_id": report.task_id,
        "topic_id": report.topic_id,
        "title": topic.title if topic else f"Report #{report.id}",
        "status": report.status,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "finished_at": report.finished_at.isoformat() if report.finished_at else None,
        "execution_duration": report.execution_duration,
        "failure_reason": report.failure_reason,
        "result_count": report.result_count,
        "retry_count": report.retry_count,
        "quality_score": report.quality_score,
        "content_md": report.content_md,
        "toc": report.toc,
        "summary": report.summary,
        "user_satisfaction": report.user_satisfaction,
        "satisfaction_notes": report.satisfaction_notes,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.post("/{report_id}/evaluate")
async def evaluate_report(
    report_id: int,
    body: EvaluateRequest,
    current_user: User = Depends(require_member),
    db: AsyncSession = Depends(get_db),
):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    task = await db.get(SearchTask, report.task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(403, "Forbidden")

    report.user_satisfaction = body.satisfaction
    report.satisfaction_notes = body.notes
    await db.commit()

    return {"id": report.id, "user_satisfaction": report.user_satisfaction}
