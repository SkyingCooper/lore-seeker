"""Celery 异步任务：执行 Agent 图并将结果入库。"""
from celery import Celery
from core.config import settings

celery_app = Celery("lore_seeker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.task_routes = {"worker.tasks.*": {"queue": "agent_tasks"}}


@celery_app.task(name="worker.tasks.run_search_pipeline", bind=True, max_retries=2)
def run_search_pipeline(self, task_id: str, user_id: str, query: str, topic_config: dict):
    import asyncio
    asyncio.run(_run(task_id, user_id, query, topic_config))


async def _run(task_id: str, user_id: str, query: str, topic_config: dict):
    from agents.graph import graph, AgentState
    from core.database import AsyncSessionLocal
    from core.redis_client import get_redis
    from core.task_redis import append_log, cleanup_workspace, init_workspace, update_context
    from db.models import SearchTask
    from services.memory_manager import archive_working_session
    from services.knowledge_service import store_report

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
                await store_report(
                    db=db,
                    task=task,
                    content_md=final_state["organized_md"],
                    toc=final_state.get("toc", []),
                    result_count=len(final_state.get("raw_results", [])),
                    quality_score=final_state.get("quality_score"),
                    token_usage=final_state.get("token_usage") or {},
                )
                await update_context(redis, int(task_id), status="completed", current_agent="planner")
                await append_log(redis, int(task_id), "worker", "任务完成并已归档工作区", interaction_type="status_update", status="completed")
                await archive_working_session(db, redis, task=task)
                await db.commit()
                await cleanup_workspace(redis, int(task_id))
            elif task:
                task.status = "failed"
                await update_context(redis, int(task_id), status="failed", failure_reason="报告内容为空")
                await append_log(redis, int(task_id), "worker", "任务执行失败：报告内容为空", interaction_type="error", status="failed")
                await archive_working_session(db, redis, task=task)
                await db.commit()
    except Exception:
        await update_context(redis, int(task_id), status="failed", failure_reason="任务执行异常")
        await append_log(redis, int(task_id), "worker", "任务执行失败", interaction_type="error", status="failed")
        async with AsyncSessionLocal() as db:
            task = await db.get(SearchTask, int(task_id))
            if task:
                task.status = "failed"
                await archive_working_session(db, redis, task=task)
                await db.commit()
        raise
