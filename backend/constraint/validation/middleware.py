"""HTTP 路由级约束校验中间件。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import json

from fastapi import Request, Response
from starlette.responses import JSONResponse


class ContractValidationMiddleware:
    """FastAPI middleware for route-specific request contract checks."""

    def __init__(self, app: Callable[[Request], Awaitable[Response]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method")
        path = scope.get("path")
        if method == "POST" and path in {"/api/v1/tasks", "/api/v1/search/start"}:
            body = await _read_body(receive)
            error = _validate_route_body(path, body)
            if error:
                response = JSONResponse(status_code=422, content={"detail": error})
                await response(scope, _replay_body(body), send)
                return
            await self.app(scope, _replay_body(body), _send_with_contract_header(send))
            return

        await self.app(scope, receive, send)


async def _read_body(receive) -> bytes:  # type: ignore[no-untyped-def]
    chunks = []
    more_body = True
    while more_body:
        message = await receive()
        chunks.append(message.get("body", b""))
        more_body = bool(message.get("more_body", False))
    return b"".join(chunks)


def _replay_body(body: bytes):  # type: ignore[no-untyped-def]
    sent = False

    async def receive() -> dict:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


def _send_with_contract_header(send):  # type: ignore[no-untyped-def]
    async def wrapped_send(message: dict) -> None:
        if message.get("type") == "http.response.start":
            headers = list(message.get("headers") or [])
            headers.append((b"x-contract-validation", b"passed"))
            message["headers"] = headers
        await send(message)

    return wrapped_send


def _validate_route_body(path: str, body: bytes) -> dict | None:
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"code": "CONTRACT_INVALID_JSON", "detail": "Request body must be valid JSON"}
    if not isinstance(payload, dict):
        return {"code": "CONTRACT_INVALID_BODY", "detail": "Request body must be a JSON object"}

    if "target_sites" in payload:
        return {"code": "CONTRACT_FIELD_DEPRECATED", "detail": "Use source_sites instead of target_sites"}
    if payload.get("search_mode", "mixed") not in {"api", "crawl", "mixed"}:
        return {"code": "CONTRACT_INVALID_SEARCH_MODE", "detail": "search_mode must be api, crawl or mixed"}
    if not isinstance(payload.get("source_sites", []), list):
        return {"code": "CONTRACT_INVALID_SOURCE_SITES", "detail": "source_sites must be a list"}
    if len(payload.get("source_sites", [])) > 5:
        return {"code": "CONTRACT_TOO_MANY_SOURCE_SITES", "detail": "source_sites supports at most 5 entries"}

    if path == "/api/v1/tasks" and not payload.get("topic_id") and not payload.get("topic_title"):
        return {"code": "CONTRACT_TOPIC_REQUIRED", "detail": "topic_id or topic_title is required"}
    if path == "/api/v1/search/start" and not payload.get("query"):
        return {"code": "CONTRACT_QUERY_REQUIRED", "detail": "query is required"}
    return None
