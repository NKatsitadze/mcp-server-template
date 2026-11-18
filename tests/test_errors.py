import pytest
from mcp.server.fastmcp.exceptions import ToolError

from example_mcp.errors import (
    UNCERTAIN_WRITE_MESSAGE,
    AppError,
    BackendAuthError,
    BackendForbiddenError,
    BackendNotFoundError,
    BackendProtocolError,
    BackendRejectedError,
    BackendUnavailableError,
    run_backend,
    run_write,
    to_tool_error,
)


def test_not_found_names_the_listing_tool() -> None:
    assert str(to_tool_error(BackendNotFoundError("x"), hint_tool="list_users")) == (
        "Not found. Call list_users to get valid ids."
    )
    assert str(to_tool_error(BackendNotFoundError("x"))) == "Not found."


def test_auth_and_rights_are_told_apart() -> None:
    assert "API_TOKEN" in str(to_tool_error(BackendAuthError("x")))
    assert "lacks rights" in str(to_tool_error(BackendForbiddenError("x")))


def test_rejected_includes_the_code() -> None:
    assert "HTTP 422 (bad-field)" in str(to_tool_error(BackendRejectedError(422, "bad-field")))


@pytest.mark.parametrize("error", [BackendUnavailableError("x"), BackendProtocolError("x")])
def test_reads_say_try_later_and_writes_say_do_not_retry(error: AppError) -> None:
    assert "try again later" in str(to_tool_error(error))
    assert str(to_tool_error(error, is_write=True)) == UNCERTAIN_WRITE_MESSAGE


async def test_run_backend_and_run_write_convert_app_errors() -> None:
    async def fail() -> None:
        raise BackendUnavailableError("down")

    with pytest.raises(ToolError, match="try again later"):
        await run_backend(fail())
    with pytest.raises(ToolError, match="Do not retry"):
        await run_write(fail())


async def test_unexpected_errors_are_not_swallowed() -> None:
    async def crash() -> None:
        raise KeyError("bug")

    with pytest.raises(KeyError):
        await run_backend(crash())
