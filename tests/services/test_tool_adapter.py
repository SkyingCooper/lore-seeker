"""Tool adapter tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.tool_adapter import (  # noqa: E402
    call_mcp_tool,
    call_named_search_tool,
    discover_enabled_tools,
    list_registered_mcp_servers,
    register_mcp_handler,
)


class ToolAdapterTest(unittest.IsolatedAsyncioTestCase):
    def test_discover_enabled_tools_for_searcher(self) -> None:
        tools = discover_enabled_tools(owner_agent="searcher")
        names = {item["name"] for item in tools}
        self.assertIn("web_search", names)
        self.assertIn("http_crawler", names)
        self.assertIn("mcp_gateway", names)

    async def test_named_search_tool_reuses_search_api_runtime(self) -> None:
        results = [{"title": "A", "url": "https://example.com", "content": "hello"}]
        with patch("services.tool_adapter.search_api", new=AsyncMock(return_value=results)):
            output = await call_named_search_tool(
                tool_name="web_search",
                caller="searcher",
                query="LoreSeeker",
                source_sites=["https://example.com"],
                task_id="1",
            )
        self.assertEqual(output, results)

    async def test_registered_mcp_server_requires_local_handler(self) -> None:
        servers = list_registered_mcp_servers()
        self.assertIsInstance(servers, list)

        register_mcp_handler(
            server="local-docs",
            tool="echo",
            handler=AsyncMock(return_value={"ok": True}),
        )

        with patch("services.tool_adapter.list_registered_mcp_servers", return_value=[
            {
                "name": "local-docs",
                "enabled": True,
                "transport": "stdio",
                "timeout_seconds": 5,
                "allowed_tools": ["echo"],
            }
        ]):
            result = await call_mcp_tool(
                caller="searcher",
                server="local-docs",
                tool="echo",
                arguments={"text": "hi"},
                task_id="2",
            )

        self.assertEqual(result["server"], "local-docs")
        self.assertEqual(result["tool"], "echo")
        self.assertTrue(result["result"]["ok"])


if __name__ == "__main__":
    unittest.main()
