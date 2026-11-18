from collections.abc import Awaitable

from mcp.server.fastmcp.exceptions import ToolError


class AppError(Exception):
    """Base for every error this server raises on purpose."""


class BackendNotFoundError(AppError):
    """HTTP 404: the id does not exist (or the account cannot see it)."""


class BackendAuthError(AppError):
    """HTTP 401: the credentials were rejected (missing, wrong or expired token)."""


class BackendForbiddenError(AppError):
    """HTTP 403: valid credentials, but no rights for this request."""


class BackendRejectedError(AppError):
    """Any other 4xx. `code` is the API's error code or message when the body has one."""

    def __init__(self, status: int, code: str | None = None) -> None:
        super().__init__(f"HTTP {status}" + (f" ({code})" if code else ""))
        self.status = status
        self.code = code


class BackendUnavailableError(AppError):
    """Network failure, timeout or 5xx: the outcome of the request is unknown."""


class BackendProtocolError(AppError):
    """The response was not the shape we expect (non-JSON, wrong type)."""


class DocsUnavailableError(AppError):
    """search_docs cannot run (no API key, no index, embedding failure); the message says why."""


UNCERTAIN_WRITE_MESSAGE = (
    "The write may or may not have been applied (backend error or no response). Do not retry: "
    "check the current state first and tell the user."
)


def to_tool_error(error: AppError, hint_tool: str | None = None, is_write: bool = False) -> ToolError:
    """Turn a backend failure into a message the model can act on: what happened and what to do next."""
    if isinstance(error, BackendNotFoundError):
        follow_up = f" Call {hint_tool} to get valid ids." if hint_tool else ""
        return ToolError(f"Not found.{follow_up}")
    if isinstance(error, BackendAuthError):
        return ToolError(
            "The API rejected API_TOKEN (missing, wrong or expired). Tell the user to fix .env and restart."
        )
    if isinstance(error, BackendForbiddenError):
        return ToolError("The configured account lacks rights for this operation.")
    if isinstance(error, BackendRejectedError):
        return ToolError(f"The API rejected the request ({error}).")
    if isinstance(error, BackendUnavailableError | BackendProtocolError):
        if is_write:
            return ToolError(UNCERTAIN_WRITE_MESSAGE)
        return ToolError("The API failed or is unreachable; try again later.")
    return ToolError(str(error))


async def run_backend[ResultT](call: Awaitable[ResultT], hint_tool: str | None = None) -> ResultT:
    try:
        return await call
    except AppError as error:
        raise to_tool_error(error, hint_tool) from error


async def run_write[ResultT](call: Awaitable[ResultT], hint_tool: str | None = None) -> ResultT:
    """Like run_backend, but an unknown outcome is reported as uncertain, never as "try again":
    many writes are not idempotent."""
    try:
        return await call
    except AppError as error:
        raise to_tool_error(error, hint_tool, is_write=True) from error
