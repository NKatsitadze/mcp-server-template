from typing import Any

import httpx

from example_mcp.auth import TokenSource
from example_mcp.errors import (
    BackendAuthError,
    BackendForbiddenError,
    BackendNotFoundError,
    BackendProtocolError,
    BackendRejectedError,
    BackendUnavailableError,
)
from example_mcp.log import get_logger
from example_mcp.settings import ServerSettings

logger = get_logger("client")

Params = dict[str, Any]


class ApiClient:
    """The ONLY place that talks HTTP to the backend. Tools call get/post/patch and never see httpx.

    A 401 is retried once, and only when the token source can produce a new token. Nothing else is
    retried: a timeout on a write may already have been applied.
    """

    def __init__(self, settings: ServerSettings, tokens: TokenSource, http: httpx.AsyncClient | None = None):
        self._tokens = tokens
        self._http = http or httpx.AsyncClient(
            base_url=settings.api_base_url, timeout=settings.http_timeout_seconds
        )

    async def get(self, path: str, params: Params | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Params | None = None) -> Any:
        return await self._request("POST", path, json=json)

    async def patch(self, path: str, json: Params | None = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def aclose(self) -> None:
        await self._http.aclose()
        await self._tokens.aclose()

    async def _request(self, method: str, path: str, params: Params | None = None, json: Any = None) -> Any:
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        token = await self._tokens.get_token()
        try:
            return await self._send(method, path, clean_params, json, token)
        except BackendAuthError:
            if not self._tokens.can_refresh:
                raise
        logger.info("API rejected the token on %s %s; refreshing once", method, path)
        await self._tokens.invalidate(token)
        return await self._send(method, path, clean_params, json, await self._tokens.get_token())

    async def _send(self, method: str, path: str, params: Params, json: Any, token: str | None) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            response = await self._http.request(
                method, path.lstrip("/"), params=params or None, json=json, headers=headers
            )
        except httpx.HTTPError as error:
            raise BackendUnavailableError(f"{method} {path}: {type(error).__name__}") from error
        return parse_response(method, path, response)


def _error_code(response: httpx.Response) -> str | None:
    """Best effort: many APIs put a code or message in the error body. Never the whole body."""
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        for key in ("code", "error", "message"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())[:100]
    return None


def parse_response(method: str, path: str, response: httpx.Response) -> Any:
    """Map HTTP status to our error types; return the parsed JSON body on success."""
    status = response.status_code
    if status == 204:
        return None
    if status == 401:
        raise BackendAuthError(f"{method} {path}")
    if status == 403:
        raise BackendForbiddenError(f"{method} {path}")
    if status == 404:
        raise BackendNotFoundError(f"{method} {path}")
    if 400 <= status < 500:
        raise BackendRejectedError(status, _error_code(response))
    if status >= 500:
        raise BackendUnavailableError(f"{method} {path}: HTTP {status}")
    try:
        return response.json()
    except ValueError as error:
        raise BackendProtocolError(f"{method} {path}: non-JSON response (HTTP {status})") from error
