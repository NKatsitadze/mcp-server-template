import httpx
import pytest
import respx
from pydantic import SecretStr

from example_mcp.auth import NoAuth, StaticToken, token_source
from example_mcp.client import ApiClient
from example_mcp.errors import (
    BackendAuthError,
    BackendForbiddenError,
    BackendNotFoundError,
    BackendProtocolError,
    BackendRejectedError,
    BackendUnavailableError,
)
from example_mcp.settings import ServerSettings
from tests.conftest import API_URL


class RefreshingTokens:
    """A source that can get a new token (like a login session), counting refreshes."""

    can_refresh = True

    def __init__(self) -> None:
        self.generation = 1
        self.invalidated: list[str | None] = []

    async def get_token(self) -> str | None:
        return f"tok{self.generation}"

    async def invalidate(self, rejected_token: str | None) -> None:
        self.invalidated.append(rejected_token)
        self.generation += 1

    async def aclose(self) -> None:
        return None


@respx.mock
async def test_get_sends_params_without_none_and_no_auth_header(settings: ServerSettings) -> None:
    route = respx.get(f"{API_URL}todos").mock(return_value=httpx.Response(200, json=[{"id": 1}]))

    result = await ApiClient(settings, NoAuth()).get("todos", {"userId": 1, "completed": False, "x": None})

    assert result == [{"id": 1}]
    request = route.calls.last.request
    assert dict(request.url.params) == {"userId": "1", "completed": "false"}
    assert "authorization" not in request.headers


@respx.mock
async def test_static_token_is_sent_as_bearer(settings: ServerSettings) -> None:
    route = respx.get(f"{API_URL}users").mock(return_value=httpx.Response(200, json=[]))

    await ApiClient(settings, StaticToken(SecretStr("abc"))).get("/users")

    assert route.calls.last.request.headers["authorization"] == "Bearer abc"


@respx.mock
async def test_base_path_is_kept(settings: ServerSettings) -> None:
    versioned = settings.model_copy(update={"api_base_url": "https://api.test/v1/"})
    route = respx.get("https://api.test/v1/users").mock(return_value=httpx.Response(200, json=[]))

    await ApiClient(versioned, NoAuth()).get("/users")

    assert route.called


@respx.mock
async def test_patch_sends_json(settings: ServerSettings) -> None:
    route = respx.patch(f"{API_URL}todos/1").mock(return_value=httpx.Response(200, json={"completed": True}))

    assert await ApiClient(settings, NoAuth()).patch("todos/1", {"completed": True}) == {"completed": True}
    assert route.calls.last.request.content == b'{"completed":true}'


@pytest.mark.parametrize(
    ("status", "body", "error_type"),
    [
        (401, {}, BackendAuthError),
        (403, {}, BackendForbiddenError),
        (404, {}, BackendNotFoundError),
        (422, {"code": "bad-field"}, BackendRejectedError),
        (500, {}, BackendUnavailableError),
        (503, {}, BackendUnavailableError),
    ],
)
@respx.mock
async def test_status_codes_map_to_error_types(settings: ServerSettings, status, body, error_type) -> None:
    respx.get(f"{API_URL}users").mock(return_value=httpx.Response(status, json=body))

    with pytest.raises(error_type):
        await ApiClient(settings, NoAuth()).get("users")


@respx.mock
async def test_rejected_error_carries_a_short_code(settings: ServerSettings) -> None:
    respx.post(f"{API_URL}posts").mock(
        return_value=httpx.Response(422, json={"message": "title  is\nrequired"})
    )

    with pytest.raises(BackendRejectedError) as error:
        await ApiClient(settings, NoAuth()).post("posts", {})

    assert error.value.code == "title is required"


@respx.mock
async def test_non_json_success_is_a_protocol_error(settings: ServerSettings) -> None:
    respx.get(f"{API_URL}users").mock(return_value=httpx.Response(200, text="<html>"))

    with pytest.raises(BackendProtocolError):
        await ApiClient(settings, NoAuth()).get("users")


@respx.mock
async def test_network_failure_is_unavailable(settings: ServerSettings) -> None:
    respx.get(f"{API_URL}users").mock(side_effect=httpx.ConnectTimeout("slow"))

    with pytest.raises(BackendUnavailableError):
        await ApiClient(settings, NoAuth()).get("users")


@respx.mock
async def test_static_token_401_is_not_retried(settings: ServerSettings) -> None:
    route = respx.get(f"{API_URL}users").mock(return_value=httpx.Response(401, json={}))

    with pytest.raises(BackendAuthError):
        await ApiClient(settings, StaticToken(SecretStr("bad"))).get("users")

    assert route.call_count == 1


@respx.mock
async def test_refreshable_401_is_retried_once_with_a_new_token(settings: ServerSettings) -> None:
    route = respx.get(f"{API_URL}users").mock(
        side_effect=[httpx.Response(401, json={}), httpx.Response(200, json=[])]
    )
    tokens = RefreshingTokens()

    assert await ApiClient(settings, tokens).get("users") == []
    assert tokens.invalidated == ["tok1"]
    assert route.calls[1].request.headers["authorization"] == "Bearer tok2"


@respx.mock
async def test_refreshable_401_twice_gives_up(settings: ServerSettings) -> None:
    route = respx.get(f"{API_URL}users").mock(return_value=httpx.Response(401, json={}))

    with pytest.raises(BackendAuthError):
        await ApiClient(settings, RefreshingTokens()).get("users")
    assert route.call_count == 2


@respx.mock
async def test_403_is_never_retried(settings: ServerSettings) -> None:
    route = respx.get(f"{API_URL}users").mock(return_value=httpx.Response(403, json={}))

    with pytest.raises(BackendForbiddenError):
        await ApiClient(settings, RefreshingTokens()).get("users")
    assert route.call_count == 1


def test_token_source_choice() -> None:
    assert isinstance(token_source(None), NoAuth)
    assert isinstance(token_source(SecretStr("k")), StaticToken)


async def test_aclose_closes_http_client(settings: ServerSettings) -> None:
    http = httpx.AsyncClient()
    await ApiClient(settings, NoAuth(), http=http).aclose()

    assert http.is_closed
