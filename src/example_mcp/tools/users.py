import asyncio
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from example_mcp.errors import run_backend
from example_mcp.formatting.common import as_list
from example_mcp.formatting.users import filter_users, format_user, format_users
from example_mcp.tools.annotations import READ_ONLY
from example_mcp.tools.backend import BackendClient

UserId = Annotated[int, Field(ge=1, description="numeric user id from list_users")]


def register(mcp: FastMCP, client: BackendClient) -> None:
    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def list_users(name_contains: str = "") -> str:
        """List users with their user id, username and company.

        - name_contains: case-insensitive part of the full name or username; empty lists everyone.
        Use the user id with get_user, list_todos or search_posts. Contact details (email, phone,
        address) are never available through this server.
        """
        users = await run_backend(client.get("users"))
        return format_users(filter_users(users, name_contains), total=len(as_list(users)))

    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def get_user(user_id: UserId) -> str:
        """Show one user's profile with their number of posts and open/completed todos.

        Get user_id from list_users.
        """
        # Fetch the user first: /posts?userId=99 returns [] instead of 404, so only this call can
        # tell the model the id does not exist.
        user = await run_backend(client.get(f"users/{user_id}"), hint_tool="list_users")
        posts, todos = await asyncio.gather(
            run_backend(client.get("posts", {"userId": user_id})),
            run_backend(client.get("todos", {"userId": user_id})),
        )
        return format_user(user, posts, todos)
