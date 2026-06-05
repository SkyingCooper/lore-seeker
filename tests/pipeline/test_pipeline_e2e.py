"""Pipeline smoke tests for create -> worker -> report -> knowledge query."""

from __future__ import annotations

import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from api.v1.tasks import TaskCreate, create_task, start_task  # noqa: E402
from api.v1.reports import get_report  # noqa: E402
from api.v1.knowledge import QueryRequest, query_knowledge  # noqa: E402
from db.models import Report, SearchTask, Topic, User  # noqa: E402
from worker.tasks import _run  # noqa: E402


class PipelineE2ETest(unittest.IsolatedAsyncioTestCase):
    async def test_member_pipeline_smoke(self) -> None:
        db = _FakeAsyncSession()
        current_user = User(id=101, username="alice", email="a@example.com", is_guest=False)
        db.users[current_user.id] = current_user

        created = await create_task(
            TaskCreate(
                query="研究 Python async 最佳实践",
                topic_title="Python Async",
                topic_keywords=["python", "asyncio"],
                topic_description="聚焦 asyncio 和生产实践",
                source_sites=["https://github.com", "https://docs.python.org"],
                search_mode="mixed",
                frequency="once",
            ),
            current_user=current_user,
            db=db,
        )
        self.assertEqual(created["status"], "pending")
        task_id = created["id"]

        with patch("worker.tasks.run_search_pipeline.delay") as delay:
            started = await start_task(task_id, current_user=current_user, db=db)
        self.assertEqual(started["status"], "fetching")
        delay.assert_called_once()

        task = db.tasks[task_id]
        topic = db.topics[task.topic_id]
        final_state = {
            "organized_md": "# Python Async\n\n## 核心结论\n使用 asyncio.TaskGroup。",
            "toc": [{"title": "核心结论", "level": 2, "anchor": "核心结论"}],
            "raw_results": [
                {"title": "Python Docs", "url": "https://docs.python.org/3/library/asyncio.html", "content": "asyncio docs", "source": "docs.python.org", "kind": "search_api", "search_mode": "api"},
            ],
            "cleaned_raw_results": [
                {"title": "Python Docs", "url": "https://docs.python.org/3/library/asyncio.html", "content": "asyncio docs", "source": "docs.python.org", "kind": "search_api", "search_mode": "api"},
            ],
            "discarded_items": [],
            "quality_score": 94.0,
            "token_usage": {"total": 42, "breakdown": {"planner": {"input_tokens": 10, "output_tokens": 5, "total": 15}}},
            "cost_usage": {"total_usd": 0.01, "breakdown": {"search": {"estimated_cost_usd": 0.01, "request_count": 1}}},
        }

        history = SimpleNamespace(id=501)
        report = Report(
            id=601,
            topic_id=topic.id,
            task_id=task.id,
            status="completed",
            result_count=1,
            quality_score=94.0,
            summary="asyncio best practices",
            content_md=final_state["organized_md"],
            toc=final_state["toc"],
            token_usage=final_state["token_usage"],
            cost_usage=final_state["cost_usage"],
        )
        db.reports[report.id] = report

        fake_graph = SimpleNamespace(ainvoke=AsyncMock(return_value=final_state))
        fake_redis = _FakeRedis()

        async def _store_report_side_effect(*args, **kwargs):
            task.status = "completed"
            return report

        with patch("agents.graph.graph", fake_graph):
            with patch("core.redis_client.get_redis", new=AsyncMock(return_value=fake_redis)):
                with patch("services.search_history_service.create_search_history", new=AsyncMock(return_value=history)) as create_history:
                    with patch("services.knowledge_service.store_report", new=AsyncMock(side_effect=_store_report_side_effect)) as store_report:
                        with patch("agents.memory_manager.run_memory_manager_agent", new=AsyncMock()) as memory_agent:
                            with patch("core.database.AsyncSessionLocal", _session_factory(db)):
                                await _run(str(task.id), str(current_user.id), task.query, {"search_mode": task.search_mode, "source_sites": task.source_sites, "frequency": task.frequency})

        self.assertEqual(db.tasks[task_id].status, "completed")
        create_history.assert_awaited_once()
        store_report.assert_awaited_once()
        memory_agent.assert_awaited_once()

        report_payload = await get_report(report.id, current_user=current_user, db=db)
        self.assertEqual(report_payload["quality_score"], 94.0)
        self.assertEqual(report_payload["result_count"], 1)

        knowledge_result = {"answer": "推荐优先使用 TaskGroup 管理并发任务。", "chunks": [{"content": "TaskGroup", "report_id": str(report.id), "rerank_score": 0.91}]}
        with patch("api.v1.knowledge.preload_retriever_context", new=AsyncMock(return_value={"preferences": [], "semantic": [], "episodic": []})):
            with patch("api.v1.knowledge.run_retriever_agent", new=AsyncMock(return_value=knowledge_result)) as retriever:
                with patch("api.v1.knowledge.record_retriever_turn", new=AsyncMock()) as record_turn:
                    answer_payload = await query_knowledge(
                        QueryRequest(query="Python async 推荐怎么做？", top_k=5, session_id="sess-1"),
                        current_user=current_user,
                        db=db,
                        redis=fake_redis,
                    )
        retriever.assert_awaited_once()
        record_turn.assert_awaited_once()
        self.assertIn("TaskGroup", answer_payload["answer"])
        self.assertEqual(answer_payload["sources"][0]["report_id"], str(report.id))


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def setex(self, key: str, _ttl: int, value: str):
        self.data[key] = value

    async def ttl(self, _key: str):
        return 3600

    async def delete(self, key: str):
        self.data.pop(key, None)


class _FakeResult:
    def __init__(self, rows=None, scalar=None) -> None:
        self._rows = rows or []
        self._scalar = scalar

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar


class _FakeAsyncSession:
    def __init__(self) -> None:
        self.users: dict[int, User] = {}
        self.topics: dict[int, Topic] = {}
        self.tasks: dict[int, SearchTask] = {}
        self.reports: dict[int, Report] = {}
        self._topic_seq = 1
        self._task_seq = 1

    def add(self, obj) -> None:
        if isinstance(obj, Topic):
            if getattr(obj, "id", None) is None:
                obj.id = self._topic_seq
                self._topic_seq += 1
            self.topics[obj.id] = obj
        elif isinstance(obj, SearchTask):
            if getattr(obj, "id", None) is None:
                obj.id = self._task_seq
                self._task_seq += 1
            self.tasks[obj.id] = obj
        elif isinstance(obj, Report):
            self.reports[obj.id] = obj

    async def flush(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def get(self, model, pk):
        if model is User:
            return self.users.get(pk)
        if model is Topic:
            return self.topics.get(pk)
        if model is SearchTask:
            return self.tasks.get(pk)
        if model is Report:
            return self.reports.get(pk)
        return None

    async def execute(self, stmt):
        description = str(stmt)
        if "FROM users" in description:
            # create_task/register style username/email uniqueness checks
            return _FakeResult(scalar=None)
        return _FakeResult([])


def _session_factory(session: _FakeAsyncSession):
    class _SessionFactory:
        def __call__(self):
            @asynccontextmanager
            async def _cm():
                yield session

            return _cm()

    return _SessionFactory()


if __name__ == "__main__":
    unittest.main()
