import pytest
from pydantic import ValidationError

from example_mcp.settings import (
    ServerSettings,
    describe_settings_error,
    parse_id_list,
    require_provider_model,
)


def make(**values: object) -> ServerSettings:
    return ServerSettings(_env_file=None, **values)


def test_defaults_run_without_any_env() -> None:
    settings = make()

    assert settings.api_base_url == "https://jsonplaceholder.typicode.com/"
    assert settings.api_token is None
    assert settings.enable_write_tools is False
    assert settings.mcp_host == "127.0.0.1"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(" https://x.test/v1 ", "https://x.test/v1/"), ("http://x.test//", "http://x.test/")],
)
def test_base_url_gets_exactly_one_trailing_slash(raw: str, expected: str) -> None:
    assert make(api_base_url=raw).api_base_url == expected


def test_base_url_must_be_http() -> None:
    with pytest.raises(ValidationError):
        make(api_base_url="ftp://x.test")


def test_blank_token_means_no_token() -> None:
    assert make(api_token="   ").api_token is None
    assert make(api_token=" abc ").api_token.get_secret_value() == "abc"


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_loopback_hosts_are_accepted(host: str) -> None:
    assert make(mcp_host=host).mcp_host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "127.0.0.2", "192.168.1.5", "example.com"])
def test_other_hosts_are_refused_until_there_is_auth(host: str) -> None:
    with pytest.raises(ValidationError, match="no auth"):
        make(mcp_host=host)


def test_provider_model_format() -> None:
    assert require_provider_model(" openai:text-embedding-3-small ") == "openai:text-embedding-3-small"
    for bad in ("text-embedding-3-small", ":model", "openai:"):
        with pytest.raises(ValueError, match="provider:model"):
            require_provider_model(bad)
    with pytest.raises(ValidationError):
        make(embedding_model="no-provider")


def test_settings_errors_never_echo_values() -> None:
    secret = "super-secret-token-value"
    with pytest.raises(ValidationError) as error:
        make(api_base_url=secret)

    message = describe_settings_error(error.value)

    assert "API_BASE_URL" in message
    assert secret not in message


def test_parse_id_list() -> None:
    assert parse_id_list(" 1, 2 ,,3 ") == frozenset({"1", "2", "3"})
    assert parse_id_list("") == frozenset()
