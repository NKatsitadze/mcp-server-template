from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from example_mcp.errors import run_backend
from example_mcp.formatting.common import as_list
from example_mcp.formatting.posts import filter_posts, format_posts
from example_mcp.tools.annotations import READ_ONLY
from example_mcp.tools.backend import BackendClient

OptionalUserId = Annotated[int | None, Field(ge=1, description="numeric user id from list_users")]


def register(mcp: FastMCP, client: BackendClient) -> None:
    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def search_posts(query: str = "", user_id: OptionalUserId = None) -> str:
        """Find posts whose title or body contains the query, with a match count.

        - query: case-insensitive text; empty matches every post.
        - user_id: only this user's posts (get it from list_users).
        Returns title, post id and user id; rows are capped at 50, the match count is not.
        """
        posts = await run_backend(client.get("posts", {"userId": user_id}))
        return format_posts(filter_posts(posts, query), total=len(as_list(posts)))
