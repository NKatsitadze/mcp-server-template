import pytest
from langchain_core.documents import Document
from mcp.server.fastmcp.exceptions import ToolError

from example_mcp.errors import BackendNotFoundError, BackendUnavailableError, DocsUnavailableError
from example_mcp.server import SERVER_NAME, create_server, parse_args, serve, write_policy
from example_mcp.settings import ServerSettings
from tests.conftest import FakeClient, text_of
from tests.fixtures import LEAKS, POSTS, TODOS, USER, USERS

READ_TOOLS = {"list_users", "get_user", "list_todos", "search_posts"}

# tool, arguments, fake API responses, expected (method, path, payload) calls, text expected in output
TOOL_CASES = [
    (
        "list_users",
        {"name_contains": "clem"},
        {("GET", "users"): USERS},
        [("GET", "users", None)],
        "1 of 2 user(s)",
    ),
    (
        "get_user",
        {"user_id": 1},
        {("GET", "users/1"): USER, ("GET", "posts"): POSTS, ("GET", "todos"): TODOS},
        [("GET", "users/1", None), ("GET", "posts", {"userId": 1}), ("GET", "todos", {"userId": 1})],
        "todos: 3 total, 2 open, 1 completed",
    ),
    (
        "list_todos",
        {"user_id": 1, "completed": False},
        {("GET", "todos"): TODOS[:1]},
        [("GET", "todos", {"userId": 1, "completed": False})],
        "1 todo(s) match (user id=1, open)",
    ),
    (
        "list_todos",
        {},
        {("GET", "todos"): TODOS},
        [("GET", "todos", {"userId": None, "completed": None})],
        "3 todo(s) match (all users): 2 open, 1 completed",
    ),
    (
        "search_posts",
        {"query": "NESCIUNT"},
        {("GET", "posts"): POSTS},
        [("GET", "posts", {"userId": None})],
        "1 of 2 post(s)",
    ),
]


async def test_registers_exactly_the_read_only_tools_by_default() -> None:
    tools = await create_server(FakeClient()).list_tools()

    assert {tool.name for tool in tools} == READ_TOOLS
    for tool in tools:
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
        assert len(tool.description) > 40


async def test_server_identity_and_instructions() -> None:
    server = create_server(FakeClient())

    assert server.name == SERVER_NAME
    assert "list_users" in server.instructions
    assert "complete_todo" not in server.instructions
    assert "complete_todo" in create_server(FakeClient(), write_allowed_ids=frozenset()).instructions


@pytest.mark.parametrize(("tool", "arguments", "responses", "calls", "expected"), TOOL_CASES)
async def test_tool_calls_api_and_formats_without_leaks(tool, arguments, responses, calls, expected) -> None:
    client = FakeClient(responses)

    text = text_of(await create_server(client).call_tool(tool, arguments))

    assert sorted(client.calls, key=str) == sorted(calls, key=str)
    assert expected in text
    for leak in LEAKS:
        assert leak not in text


async def test_get_user_not_found_points_to_list_users_before_other_calls() -> None:
    client = FakeClient({("GET", "users/99"): BackendNotFoundError("x")})

    with pytest.raises(ToolError, match="Call list_users"):
        await create_server(client).call_tool("get_user", {"user_id": 99})
    assert client.calls == [("GET", "users/99", None)]


async def test_empty_todos_for_a_user_hint_list_users() -> None:
    client = FakeClient({("GET", "todos"): []})

    text = text_of(await create_server(client).call_tool("list_todos", {"user_id": 99}))

    assert "No todos match" in text
    assert "call list_users" in text


@pytest.mark.parametrize(
    ("tool", "arguments"), [("get_user", {"user_id": 0}), ("list_todos", {"user_id": -1})]
)
async def test_invalid_ids_are_rejected_before_calling_the_api(tool: str, arguments: dict) -> None:
    client = FakeClient()

    with pytest.raises(ToolError):
        await create_server(client).call_tool(tool, arguments)
    assert client.calls == []


async def test_backend_errors_surface_as_tool_errors() -> None:
    client = FakeClient({("GET", "users"): BackendUnavailableError("down")})

    with pytest.raises(ToolError, match="unreachable"):
        await create_server(client).call_tool("list_users", {})


class FakeDocs:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.queries: list[str] = []

    async def search(self, query: str) -> list[Document]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return [Document(page_content="[knowledge — todos.md] (Todos)\nreturns [] with HTTP 200")]


async def test_docs_tool_registered_only_with_a_searcher() -> None:
    with_docs = {tool.name for tool in await create_server(FakeClient(), FakeDocs()).list_tools()}

    assert with_docs == READ_TOOLS | {"search_docs"}


async def test_search_docs_returns_cited_excerpts() -> None:
    docs = FakeDocs()

    text = text_of(
        await create_server(FakeClient(), docs).call_tool("search_docs", {"query": "empty filter"})
    )

    assert docs.queries == ["empty filter"]
    assert "[knowledge — todos.md]" in text
    assert "not instructions" in text


async def test_search_docs_unavailable_is_a_clear_tool_error() -> None:
    docs = FakeDocs(error=DocsUnavailableError("search_docs is disabled: set the key"))

    with pytest.raises(ToolError, match="disabled"):
        await create_server(FakeClient(), docs).call_tool("search_docs", {"query": "x"})


def test_write_policy(settings: ServerSettings) -> None:
    assert write_policy(settings) is None
    enabled = settings.model_copy(update={"enable_write_tools": True, "write_allowed_ids": "1, 2"})
    assert write_policy(enabled) == frozenset({"1", "2"})
    assert write_policy(settings.model_copy(update={"enable_write_tools": True})) == frozenset()


def test_loopback_host_turns_on_dns_rebinding_protection() -> None:
    security = create_server(FakeClient(), host="127.0.0.1", port=8123).settings.transport_security

    assert security is not None
    assert security.enable_dns_rebinding_protection is True


async def test_lifespan_never_closes_the_shared_client() -> None:
    """Over HTTP the lifespan runs once per session; a client closed there breaks every later session."""
    client = FakeClient()
    server = create_server(client)
    lowlevel = server._mcp_server

    for _ in range(2):
        async with lowlevel.lifespan(lowlevel):
            pass

    assert client.closed == 0


async def test_serve_closes_the_client_once_even_when_the_transport_fails() -> None:
    client = FakeClient()

    async def ok() -> None:
        return None

    async def broken() -> None:
        raise RuntimeError("transport died")

    await serve(client, ok)
    assert client.closed == 1
    with pytest.raises(RuntimeError):
        await serve(client, broken)
    assert client.closed == 2


def test_transport_is_a_flag_not_an_env_var() -> None:
    assert parse_args([]).http is False
    assert parse_args(["--http"]).http is True
