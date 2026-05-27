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
    from db.models import SearchTask
    from services.knowledge_service import store_report
    from sqlalchemy import select
    import uuid

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
        "iteration": 0,
        "final": False,
    }

    final_state = await graph.ainvoke(state)

    async with AsyncSessionLocal() as db:
        task = await db.get(SearchTask, uuid.UUID(task_id))
        if task and final_state.get("organized_md"):
            await store_report(
                db=db,
                task=task,
                title=query,
                content_md=final_state["organized_md"],
                toc=final_state.get("toc", []),
            )
