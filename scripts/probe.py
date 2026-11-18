"""Live, read-only check of the configured API: uv run python scripts/probe.py

Calls one endpoint and prints only the SHAPE of the response (keys and types), never values, so it is
safe to run against real data and paste into a ticket. Use it to read a response shape before writing
a formatter for it.
"""

import asyncio
import sys
from typing import Any

from example_mcp.auth import token_source
from example_mcp.client import ApiClient
from example_mcp.errors import AppError
from example_mcp.settings import ServerSettings, load_env_file

DEFAULT_PATH = "users"


def describe_shape(value: Any, depth: int = 0, max_depth: int = 4) -> str:
    """Keys and types only, e.g. {id: int, company: {name: str}} or list[3] of {...}."""
    if depth >= max_depth:
        return "…"
    if isinstance(value, dict):
        inner = ", ".join(
            f"{key}: {describe_shape(item, depth + 1, max_depth)}" for key, item in value.items()
        )
        return "{" + inner + "}"
    if isinstance(value, list):
        return (
            f"list[{len(value)}] of {describe_shape(value[0], depth + 1, max_depth)}" if value else "list[0]"
        )
    return type(value).__name__


async def probe(path: str) -> int:
    load_env_file()
    settings = ServerSettings()
    client = ApiClient(settings, token_source(settings.api_token))
    try:
        result = await client.get(path)
    except AppError as error:
        print(f"❌ GET {path}: {type(error).__name__}: {error}")
        return 1
    finally:
        await client.aclose()
    print(f"✅ GET {settings.api_base_url}{path}\n{describe_shape(result)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(probe(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)))
