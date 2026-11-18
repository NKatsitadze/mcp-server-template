from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
ALLOWED_URL_SCHEMES = ("http://", "https://")
# Exactly the hosts for which FastMCP turns on DNS-rebinding protection by itself. Any other host
# (0.0.0.0, a LAN address, even 127.0.0.2) would serve the tools unprotected and without auth.
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def load_env_file() -> None:
    """Export .env into os.environ (real env vars win).

    pydantic-settings reads .env into our settings objects but does not export it, while model and
    embedding providers (OpenAI, Anthropic, LangSmith) read their keys from the process environment.
    Call this in every entry point before building a provider client. Uses an explicit path, never
    find_dotenv(), so the result does not depend on the caller's working directory.
    """
    load_dotenv(ENV_FILE, override=False)


def require_provider_model(value: str) -> str:
    """'openai:text-embedding-3-small' style strings, as init_chat_model / init_embeddings expect."""
    provider, separator, model = value.strip().partition(":")
    if not separator or not provider or not model:
        raise ValueError("must look like provider:model, e.g. openai:text-embedding-3-small")
    return f"{provider}:{model}"


class ServerSettings(BaseSettings):
    """Server configuration. Loaded from env vars, falling back to the project's .env file."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # The example backend: a free public fake API, so the template runs with no .env at all.
    api_base_url: str = "https://jsonplaceholder.typicode.com"
    # Optional bearer token for a real API. Empty = no Authorization header.
    api_token: SecretStr | None = None
    http_timeout_seconds: float = Field(default=20, gt=0)

    # HTTP transport (only with `example-mcp --http`). Loopback only until the server has OAuth.
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8000, ge=1, le=65535)

    # Write tools: off unless explicitly enabled. When WRITE_ALLOWED_IDS is set (comma-separated ids),
    # the server refuses writes to any other id: a guard enforced next to the action.
    enable_write_tools: bool = False
    write_allowed_ids: str = ""

    # search_docs: on by default; it loads lazily and explains itself when the key or index is missing.
    docs_search: bool = True
    embedding_model: str = "openai:text-embedding-3-small"
    docs_index_dir: Path = PROJECT_ROOT / "data" / "chroma"

    @field_validator("api_base_url")
    @classmethod
    def _normalize_base_url(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith(ALLOWED_URL_SCHEMES):
            raise ValueError("must start with http:// or https://")
        # A trailing slash makes httpx append request paths to any base path (https://x/v1/ + users).
        return stripped.rstrip("/") + "/"

    @field_validator("api_token")
    @classmethod
    def _empty_token_is_none(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value().strip():
            return None
        return SecretStr(value.get_secret_value().strip())

    @field_validator("mcp_host")
    @classmethod
    def _loopback_only(cls, value: str) -> str:
        host = value.strip()
        if host not in LOOPBACK_HOSTS:
            raise ValueError(
                f"must be one of {', '.join(LOOPBACK_HOSTS)}: the HTTP transport has no auth yet"
            )
        return host

    @field_validator("embedding_model")
    @classmethod
    def _provider_model(cls, value: str) -> str:
        return require_provider_model(value)


def describe_settings_error(error: ValidationError) -> str:
    """List invalid fields without echoing input values (they may contain a token)."""
    problems = [
        f"{'.'.join(str(part) for part in issue['loc']).upper()}: {issue['msg']}" for issue in error.errors()
    ]
    return "Invalid configuration (check .env): " + "; ".join(problems)


def parse_id_list(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())
