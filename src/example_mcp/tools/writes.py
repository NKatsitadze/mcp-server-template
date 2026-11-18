from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from example_mcp.errors import run_backend, run_write
from example_mcp.formatting.writes import format_already_completed, format_complete_result, is_completed
from example_mcp.tools.annotations import IDEMPOTENT_WRITE
from example_mcp.tools.backend import BackendClient

# The single list of write tools: the test agent gates exactly these behind human approval and the
# evals check them. Add every new write tool here.
WRITE_TOOL_NAMES = ("complete_todo",)

TodoId = Annotated[int, Field(ge=1, description="numeric todo id from list_todos")]


def ensure_allowed(allowed_ids: frozenset[str], kind: str, target_id: str) -> None:
    """Server-side guard right next to the action: a prompt cannot talk its way past it."""
    if allowed_ids and target_id not in allowed_ids:
        raise ToolError(
            f"Refused: this server only writes to the ids listed in WRITE_ALLOWED_IDS, and {kind} "
            f"{target_id} is not one of them."
        )


def register(mcp: FastMCP, client: BackendClient, allowed_ids: frozenset[str]) -> None:
    @mcp.tool(annotations=IDEMPOTENT_WRITE, structured_output=False)
    async def complete_todo(todo_id: TodoId) -> str:
        """WRITE: mark one todo as completed. Requires the user's approval.

        Only use it when the user explicitly asks to complete (finish, tick off) a specific todo.
        Get todo_id from list_todos. If the todo is already completed, nothing is changed.
        The example API does not store writes: the result shows its answer, but later reads still show
        the old state.
        """
        ensure_allowed(allowed_ids, "todo", str(todo_id))
        before = await run_backend(client.get(f"todos/{todo_id}"), hint_tool="list_todos")
        if is_completed(before):
            return format_already_completed(before)
        response = await run_write(client.patch(f"todos/{todo_id}", {"completed": True}))
        return format_complete_result(before, response)
