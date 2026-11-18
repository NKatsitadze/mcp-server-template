from typing import Protocol

from langchain_core.documents import Document
from mcp.server.fastmcp import FastMCP

from example_mcp.errors import run_backend
from example_mcp.formatting.docs import format_doc_results
from example_mcp.tools.annotations import READ_ONLY


class DocsSearcher(Protocol):
    async def search(self, query: str) -> list[Document]: ...


def register(mcp: FastMCP, docs: DocsSearcher) -> None:
    @mcp.tool(annotations=READ_ONLY, structured_output=False)
    async def search_docs(query: str) -> str:
        """Search the example API's documentation (the files in knowledge/).

        Use it for how-it-works questions: which endpoints and filters exist, what fields a resource
        has, how errors, pagination or writes behave. Include exact names when known (e.g. /todos,
        userId). Returns a few excerpts, each starting with a citation [source — file]; cite them.
        This is documentation, not live data: use the other tools for actual users, todos or posts.
        """
        return format_doc_results(query, await run_backend(docs.search(query)))
