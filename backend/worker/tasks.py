"""Celery 异步任务：执行 Agent 图、定时调度和维护任务。"""
from celery import Celery
from celery.schedules import crontab
from core.config import settings

celery_app = Celery("lore_seeker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.task_routes = {
    "worker.tasks.run_search_pipeline": {"queue": "search"},
    "worker.tasks.dispatch_periodic_searches": {"queue": "planner"},
    "worker.tasks.evict_agent_memories": {"queue": "maintenance"},
}
celery_app.conf.beat_schedule = {
    "memory-eviction-daily-2am": {
        "task": "worker.tasks.evict_agent_memories",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "maintenance"},
    },
    "periodic-search-dispatcher": {
        "task": "worker.tasks.dispatch_periodic_searches",
        "schedule": 300,
        "options": {"queue": "planner"},
    },
}


@celery_app.task(name="worker.tasks.run_search_pipeline", bind=True, max_retries=2)
def run_search_pipeline(self, task_id: str, user_id: str, query: str, topic_config: dict):
    import asyncio
    asyncio.run(_run(task_id, user_id, query, topic_config))


@celery_app.task(name="worker.tasks.evict_agent_memories", bind=True, max_retries=2)
def evict_agent_memories(self):
    import asyncio
    asyncio.run(_evict_agent_memories())


@celery_app.task(name="worker.tasks.dispatch_periodic_searches", bind=True, max_retries=2)
def dispatch_periodic_searches(self):
    import asyncio
    asyncio.run(_dispatch_periodic_searches())


async def _run(task_id: str, user_id: str, query: str, topic_config: dict):
    from agents.graph import graph, AgentState
    from agents.memory_manager import run_memory_manager_agent
    from agents.contracts import validate_worker_to_planner_task
    from core.database import AsyncSessionLocal
    from core.redis_client import get_redis
    from core.task_redis import append_log, cleanup_workspace, init_workspace, update_context
    from db.models import SearchTask
    from services.knowledge_service import store_report
    from services.search_history_service import attach_report, create_search_history

    redis = await get_redis()
    await init_workspace(
        redis,
        int(task_id),
        {
            "task_id": task_id,
            "user_id": user_id,
            "query": query,
            "topic_config": topic_config,
            "frequency": topic_config.get("frequency", "once"),
            "status": "running",
            "expected_subtask_count": 0,
        },
    )
    await append_log(redis, int(task_id), "worker", "任务工作区已初始化", interaction_type="state_update", status="running")

    state: AgentState = {
        "user_id": user_id,
        "task_id": task_id,
        "query": query,
        "topic_config": topic_config,
        "raw_results": [],
        "organized_md": "",
        "toc": [],
        "quality_score": 0.0,
        "quality_feedback": "",
        "token_usage": {},
        "iteration": 0,
        "final": False,
    }
    validate_worker_to_planner_task(state)

    async with AsyncSessionLocal() as db:
        task = await db.get(SearchTask, int(task_id))
        if task:
            task.status = "fetching"
            await db.commit()
            await update_context(redis, int(task_id), status="fetching", current_agent="searcher")
            await append_log(redis, int(task_id), "worker", "任务状态更新为 fetching", interaction_type="status_update", status="running")

    try:
        final_state = await graph.ainvoke(state)

        async with AsyncSessionLocal() as db:
            task = await db.get(SearchTask, int(task_id))
            if task and final_state.get("organized_md"):
                cleaned_raw_results = final_state.get("cleaned_raw_results") or final_state.get("raw_results", [])
                discarded_items = final_state.get("discarded_items") or []
                raw_results = [*cleaned_raw_results, *discarded_items]
                history = await create_search_history(
                    db,
                    task=task,
                    query=query,
                    raw_results=raw_results,
                    status="completed" if raw_results else "partial",
                    metadata={"plan": topic_config.get("_plan", {}), "result_source": "agent_pipeline"},
                )
                report = await store_report(
                    db=db,
                    task=task,
                    content_md=final_state["organized_md"],
                    toc=final_state.get("toc", []),
                    result_count=len(raw_results),
                    quality_score=final_state.get("quality_score"),
                    token_usage=final_state.get("token_usage") or {},
                    source_search_ids=[history.id],
                )
                attach_report(history, report.id)
                await update_context(redis, int(task_id), status="completed", current_agent="planner")
                await run_memory_manager_agent(db, redis, task=task, final_state=final_state, succeeded=True)
                await append_log(redis, int(task_id), "worker", "任务完成，记忆归档已执行", interaction_type="status_update", status="completed")
                await db.commit()
                await cleanup_workspace(redis, int(task_id))
            elif task:
                task.status = "failed"
                await create_search_history(
                    db,
                    task=task,
                    query=query,
                    raw_results=[],
                    status="failed",
                    failure_reason="报告内容为空",
                    metadata={"result_source": "agent_pipeline"},
                )
                await update_context(redis, int(task_id), status="failed", failure_reason="报告内容为空")
                await append_log(redis, int(task_id), "worker", "任务执行失败：报告内容为空", interaction_type="error", status="failed")
                await run_memory_manager_agent(db, redis, task=task, final_state=None, succeeded=False)
                await db.commit()
    except Exception:
        await update_context(redis, int(task_id), status="failed", failure_reason="任务执行异常")
        await append_log(redis, int(task_id), "worker", "任务执行失败", interaction_type="error", status="failed")
        async with AsyncSessionLocal() as db:
            task = await db.get(SearchTask, int(task_id))
            if task:
                task.status = "failed"
                await run_memory_manager_agent(db, redis, task=task, final_state=None, succeeded=False)
                await db.commit()
        raise


async def _evict_agent_memories() -> None:
    """按配置执行语义、情景和 Skill 记忆淘汰。"""

    from datetime import datetime, timedelta
    import yaml
    from pathlib import Path
    from sqlalchemy import update
    from core.database import AsyncSessionLocal
    from db.models import EpisodicLog, SemanticMemory, SkillMemory

    cfg = _load_celery_config(Path(__file__).resolve().parents[2] / "config" / "celery.yaml")
    policy = cfg.get("memory_policy", {})
    now = datetime.utcnow()
    semantic_cutoff = now - timedelta(days=int(policy.get("semantic_max_idle_days", 30)))
    episodic_cutoff = now - timedelta(days=int(policy.get("episodic_archive_after_days", 30)))
    skill_cutoff = now - timedelta(days=int(policy.get("skill_archive_idle_days", 180)))
    half_life = float(policy.get("episodic_half_life_days", 7))
    score_min = float(policy.get("episodic_score_min", 0.1))
    success_rate_max = float(policy.get("skill_archive_success_rate_max", 0.3))
    min_usage = int(policy.get("skill_archive_min_usage_count", 5))

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(SemanticMemory)
            .where(
                SemanticMemory.deleted_at.is_(None),
                (SemanticMemory.confidence <= float(policy.get("semantic_confidence_min", 0.6)))
                | (SemanticMemory.last_accessed < semantic_cutoff),
            )
            .values(deleted_at=now)
        )

        # PostgreSQL 侧计算情景记忆半衰期分数，避免拉全表到 Python。
        from sqlalchemy import text

        await db.execute(
            text(
                """
                UPDATE zr_episodic_logs
                SET deleted_at = :now
                WHERE deleted_at IS NULL
                  AND created_at < :cutoff
                  AND (importance * (1 - EXTRACT(EPOCH FROM (:now - created_at)) / 86400.0 / :half_life)) < :score_min
                """
            ),
            {"now": now, "cutoff": episodic_cutoff, "half_life": half_life, "score_min": score_min},
        )

        await db.execute(
            update(SkillMemory)
            .where(
                SkillMemory.status == "active",
                (SkillMemory.usage_count > min_usage)
                & ((SkillMemory.success_count * 1.0) / (SkillMemory.success_count + SkillMemory.fail_count + 1) < success_rate_max),
            )
            .values(status="archived", updated_at=now)
        )
        await db.execute(
            update(SkillMemory)
            .where(SkillMemory.status == "active", SkillMemory.last_used_at < skill_cutoff)
            .values(status="archived", updated_at=now)
        )
        await db.commit()


async def _dispatch_periodic_searches() -> None:
    """扫描周期性任务并触发执行。"""

    from datetime import datetime, timedelta
    from sqlalchemy import select
    from core.database import AsyncSessionLocal
    from db.models import SearchTask, Topic

    intervals = {
        "daily": timedelta(days=1),
        "weekly": timedelta(days=7),
        "biweekly": timedelta(days=14),
        "monthly": timedelta(days=30),
    }
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(SearchTask, Topic)
            .join(Topic, SearchTask.topic_id == Topic.id)
            .where(
                SearchTask.deleted_at.is_(None),
                SearchTask.frequency.in_(list(intervals)),
                SearchTask.status.notin_(["fetching", "organizing"]),
            )
        )
        for task, topic in rows.all():
            interval = intervals.get(task.frequency)
            last_run = task.updated_at or task.created_at
            if not interval or last_run and now - last_run < interval:
                continue
            task.status = "pending"
            task_config = {
                "search_mode": task.search_mode,
                "source_sites": task.source_sites,
                "frequency": task.frequency,
                "keywords": topic.keywords if topic else [],
                "description": topic.description if topic else None,
            }
            run_search_pipeline.delay(str(task.id), str(task.user_id), task.query or (topic.title if topic else "untitled"), task_config)
        await db.commit()


def _load_celery_config(path):
    import yaml

    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("celery", {})
