import logging
import re
import sys

LOGGER_NAME = "example_mcp"
MASK = "***"

_REDACTIONS = (
    re.compile(r"(authorization:\s*(?:bearer\s+)?).+", re.IGNORECASE),
    re.compile(r"(bearer\s+)[\w.~+/=-]+", re.IGNORECASE),
    re.compile(
        r"(?<!\w)(\"?(?:access_?token|api_?token|api_?key|token|password|secret)\"?\s*[:=]\s*\"?)[^\"',\s}]+",
        re.IGNORECASE,
    ),
    re.compile(r"((?:set-)?cookie:\s*).+", re.IGNORECASE),
    re.compile(r"()eyJ[\w-]+\.[\w-]+\.[\w-]+"),
)


def redact(message: str) -> str:
    for pattern in _REDACTIONS:
        message = pattern.sub(rf"\g<1>{MASK}", message)
    return message


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Send our logs to stderr only: in stdio mode stdout carries the MCP JSON-RPC stream, and one
    stray print() there corrupts it."""
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False

    for noisy_logger in ("httpx", "httpcore"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
