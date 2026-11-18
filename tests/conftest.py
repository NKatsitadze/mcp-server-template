from typing import Any

import pytest

from example_mcp.settings import ServerSettings

API_URL = "https://api.test/"

# Env vars that would make a test depend on the developer's shell or .env.
ISOLATED_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "MODEL",
    "JUDGE_MODEL",
    "API_BASE_URL",
    "API_TOKEN",
    "ENABLE_WRITE_TOOLS",
    "WRITE_ALLOWED_IDS",
    "DOCS_SEARCH",
    "EMBEDDING_MODEL",
    "DOCS_INDEX_DIR",
    "MCP_HOST",
    "MCP_PORT",
    "LANGSMITH_TRACING",
)


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test sees real keys or the developer's .env: unset the vars and make load_env_file a no-op.
    Settings in tests are built with _env_file=None for the same reason."""
    for name in ISOLATED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("example_mcp.settings.load_dotenv", lambda *args, **kwargs: False)


@pytest.fixture
def settings() -> ServerSettings:
    return ServerSettings(_env_file=None, api_base_url=API_URL)


class FakeClient:
    """Records every call; answers from `responses` keyed by (method, path), or raises if the value
    is an exception."""

    def __init__(self, responses: dict[tuple[str, str], Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, str, Any]] = []
        self.closed = 0

    async def _answer(self, method: str, path: str, payload: Any) -> Any:
        self.calls.append((method, path, payload))
        result = self.responses.get((method, path))
        if isinstance(result, Exception):
            raise result
        return result

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._answer("GET", path, params)

    async def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._answer("POST", path, json)

    async def patch(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return await self._answer("PATCH", path, json)

    async def aclose(self) -> None:
        self.closed += 1


def text_of(result: Any) -> str:
    """FastMCP.call_tool returns content blocks (or a (blocks, structured) tuple)."""
    blocks = result[0] if isinstance(result, tuple) else result
    return "\n".join(block.text for block in blocks)
