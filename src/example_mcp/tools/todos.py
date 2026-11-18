from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from example_mcp.errors import run_backend
from example_mcp.formatting.common import as_list
from example_mcp.formatting.todos import describe_filters, format_todos
from example_mcp.tools.annotations import READ_ONLY
from example_mcp.tools.backend import BackendClient

OptionalUserId = Annotated[int | None, Field(ge=1, description="numeric user id from list_users")]


def register(mcp: FastMCP, client: BackendClient) -> None:
    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def list_todos(user_id: OptionalUserId = None, completed: bool | None = None) -> str:
        """List todos with open/completed counts.

        - user_id: only this user's todos (get it from list_users); omit for everyone.
        - completed: true = only completed, false = only open; omit for both.
        Prefer these filters over reading the whole list: rows are capped at 50, the counts are not.
        """
        todos = await run_backend(client.get("todos", {"userId": user_id, "completed": completed}))
        text = format_todos(todos, describe_filters(user_id, completed))
        if user_id is not None and not as_list(todos):
            # The API answers an unknown user id with an empty list, not a 404.
            text += " If the user id is unknown, call list_users to get valid ids."
        return text
