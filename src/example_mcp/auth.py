from typing import Protocol

from pydantic import SecretStr


class TokenSource(Protocol):
    """Where the client gets credentials. get_token() returns None for "send no Authorization header".

    can_refresh tells the client whether a 401 is worth one retry: only a source that can get a NEW
    token (a login session, an OAuth refresh) should say yes. A static key would just fail twice.
    For a login-based source, see docs/PATTERNS.md (one lock, never retry a failed login, one re-login).
    """

    @property
    def can_refresh(self) -> bool: ...

    async def get_token(self) -> str | None: ...

    async def invalidate(self, rejected_token: str | None) -> None: ...

    async def aclose(self) -> None: ...


class NoAuth:
    """For public APIs: no Authorization header at all."""

    can_refresh = False

    async def get_token(self) -> str | None:
        return None

    async def invalidate(self, rejected_token: str | None) -> None:
        return None

    async def aclose(self) -> None:
        return None


class StaticToken:
    """A fixed API key / bearer token from .env (API_TOKEN). It cannot be refreshed."""

    can_refresh = False

    def __init__(self, token: SecretStr) -> None:
        self._token = token

    async def get_token(self) -> str | None:
        return self._token.get_secret_value()

    async def invalidate(self, rejected_token: str | None) -> None:
        return None

    async def aclose(self) -> None:
        return None


def token_source(api_token: SecretStr | None) -> TokenSource:
    return StaticToken(api_token) if api_token is not None else NoAuth()
