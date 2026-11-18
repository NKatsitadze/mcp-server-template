"""Start the real server as a subprocess and talk MCP to it over stdio.

This is the test that catches stdout pollution: one print() or chatty import (chroma, langchain,
dotenv) on stdout corrupts the JSON-RPC stream, and every unit test would still pass.
"""

import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from example_mcp.settings import PROJECT_ROOT

SERVER_ENV = {
    # Port 9 on loopback refuses connections at once: no internet needed, and the error path is tested.
    "API_BASE_URL": "http://127.0.0.1:9",
    "ENABLE_WRITE_TOOLS": "false",
    "DOCS_SEARCH": "true",
    "DOCS_INDEX_DIR": str(PROJECT_ROOT / "data" / "e2e-no-index"),
}


async def test_server_speaks_mcp_over_stdio() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "example_mcp"], env=SERVER_ENV)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        init = await session.initialize()
        tools = {tool.name for tool in (await session.list_tools()).tools}
        result = await session.call_tool("list_users", {})

    assert init.serverInfo.name == "example-mcp"
    assert {"list_users", "get_user", "list_todos", "search_posts", "search_docs"} <= tools
    assert "complete_todo" not in tools
    assert result.isError is True
    assert "unreachable" in result.content[0].text
