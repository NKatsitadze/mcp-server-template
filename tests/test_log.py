import logging
import sys

import pytest

from example_mcp.log import MASK, configure_logging, get_logger, redact


@pytest.mark.parametrize(
    "message",
    [
        "Authorization: Bearer abc.def.ghi",
        "sending bearer sk_live_1234567890",
        '{"api_token": "abc123"}',
        "password=hunter22",
        "Set-Cookie: session=abc",
        "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
    ],
)
def test_redact_masks_credentials(message: str) -> None:
    redacted = redact(message)

    assert MASK in redacted
    for secret in ("abc.def.ghi", "sk_live_1234567890", "abc123", "hunter22", "session=abc", "c2lnbmF0dXJl"):
        assert secret not in redacted


def test_redact_keeps_ordinary_text() -> None:
    assert redact("GET users/1 returned 404") == "GET users/1 returned 404"


def test_logs_go_to_stderr_never_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging()
    handler = logging.getLogger("example_mcp").handlers[0]

    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stderr

    get_logger("test").warning("token=abc123")
    captured = capsys.readouterr()
    assert captured.out == ""
