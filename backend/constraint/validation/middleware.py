"""约束校验中间件骨架。

当前中间件不默认拦截所有 HTTP 请求；它提供一个可插拔入口，后续可按路由或 header
启用 contract 校验，避免在未完成全链路适配前影响现有 API。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response


class ContractValidationMiddleware:
    """FastAPI middleware placeholder for request/response contract validation.

    Usage:
        app.add_middleware(ContractValidationMiddleware)

    The first production use should bind route path -> contract schema explicitly.
    """

    def __init__(self, app: Callable[[Request], Awaitable[Response]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        await self.app(scope, receive, send)
