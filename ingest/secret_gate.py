"""Fail-closed check run on every file and chunk before its text is embedded.

Chunk text is sent to the embeddings API and stored on disk, so a file that looks like it holds a
credential is skipped whole, never redacted and kept: an uncertain file stays out. Only the pattern
names are reported, never the matched value. Expect false positives on look-alikes; that is the price
of failing closed. Add patterns for your own data (see the commented example).
"""

import re
from dataclasses import dataclass

SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "credentialed-uri": re.compile(
        r"\b(?:mongodb(?:\+srv)?|rediss?|amqp|postgres(?:ql)?|mysql)://[^\s'\"/@]*:[^\s'\"@]+@"
    ),
    "url-with-userinfo": re.compile(r"https?://[^\s'\"/@]+@"),
    # Passwords can be short; keys are long. Schema words such as apiKey: 'string' stay below the
    # 16-character key threshold, so ordinary code and docs are not skipped.
    "password-literal": re.compile(
        r"(?:password|passwd)['\"]?\s*[:=]\s*['\"][^'\"\s]{6,}['\"]", re.IGNORECASE
    ),
    "key-literal": re.compile(
        r"(?:secret|apikey|api_key|token|access_key|hmac_key)['\"]?\s*[:=]\s*['\"][^'\"\s]{16,}['\"]",
        re.IGNORECASE,
    ),
    "bearer-token": re.compile(r"bearer\s+[\w.~+/=-]{20,}", re.IGNORECASE),
    "provider-key": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16})\b"),
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "jwt": re.compile(r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]+"),
    "base64-blob": re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"),
    # Example of a data pattern for your domain, e.g. an 11-digit national id number:
    # "personal-number": re.compile(r"(?<!\d)\d{11}(?!\d)"),
}


@dataclass(frozen=True)
class SkippedFile:
    path: str
    patterns: tuple[str, ...]


def find_secrets(text: str) -> list[str]:
    """Names of the patterns that match; empty when the text is safe to embed."""
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]
