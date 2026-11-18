import pytest
from mcp.server.fastmcp.exceptions import ToolError

from example_mcp.errors import BackendUnavailableError
from example_mcp.server import create_server
from example_mcp.tools.writes import WRITE_TOOL_NAMES
from tests.conftest import FakeClient, text_of

OPEN_TODO = {"userId": 1, "id": 1, "title": "first todo", "completed": False}
DONE_TODO = {**OPEN_TODO, "completed": True}


def writable(client: FakeClient, allowed: frozenset[str] = frozenset({"1"})):
    return create_server(client, write_allowed_ids=allowed)


async def test_write_tools_are_registered_only_when_enabled() -> None:
    read_only = {tool.name for tool in await create_server(FakeClient()).list_tools()}
    tools = {tool.name: tool for tool in await writable(FakeClient()).list_tools()}

    assert not read_only & set(WRITE_TOOL_NAMES)
    assert set(WRITE_TOOL_NAMES) <= set(tools)
    annotations = tools["complete_todo"].annotations
    assert annotations.destructiveHint is True
    assert annotations.readOnlyHint is False


async def test_complete_todo_reads_then_patches() -> None:
    client = FakeClient({("GET", "todos/1"): OPEN_TODO, ("PATCH", "todos/1"): DONE_TODO})

    text = text_of(await writable(client).call_tool("complete_todo", {"todo_id": 1}))

    assert client.calls == [("GET", "todos/1", None), ("PATCH", "todos/1", {"completed": True})]
    assert "before: completed=no" in text
    assert "API response: completed=yes" in text
    assert "does not persist" in text


async def test_already_completed_todo_is_not_written() -> None:
    client = FakeClient({("GET", "todos/1"): DONE_TODO})

    text = text_of(await writable(client).call_tool("complete_todo", {"todo_id": 1}))

    assert "already completed" in text
    assert [call[0] for call in client.calls] == ["GET"]


async def test_allowlist_refuses_before_any_api_call() -> None:
    client = FakeClient()

    with pytest.raises(ToolError, match="WRITE_ALLOWED_IDS"):
        await writable(client).call_tool("complete_todo", {"todo_id": 2})
    assert client.calls == []


async def test_empty_allowlist_allows_any_id() -> None:
    client = FakeClient({("GET", "todos/7"): {**OPEN_TODO, "id": 7}, ("PATCH", "todos/7"): DONE_TODO})

    await writable(client, frozenset()).call_tool("complete_todo", {"todo_id": 7})

    assert ("PATCH", "todos/7", {"completed": True}) in client.calls


async def test_failed_write_says_do_not_retry() -> None:
    client = FakeClient(
        {("GET", "todos/1"): OPEN_TODO, ("PATCH", "todos/1"): BackendUnavailableError("timeout")}
    )

    with pytest.raises(ToolError, match="Do not retry"):
        await writable(client).call_tool("complete_todo", {"todo_id": 1})
