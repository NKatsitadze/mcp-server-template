from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

MISSING = "—"
NEVER = "never"
UNKNOWN = "unknown"
MAX_ROWS = 50
MAX_TEXT_LENGTH = 200


def display(value: Any) -> str:
    """Render one value on a single line. User-entered text is flattened and truncated so it
    cannot fake extra lines or bury the output."""
    if value is None or value == "":
        return MISSING
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list | tuple):
        return ", ".join(display(item) for item in value) if value else MISSING
    text = " ".join(str(value).split())
    if not text:
        return MISSING
    return text if len(text) <= MAX_TEXT_LENGTH else text[: MAX_TEXT_LENGTH - 1] + "…"


def format_date(value: Any, missing: str = NEVER) -> str:
    """Unix seconds or ISO strings to a YYYY-MM-DD date.

    `missing` labels 0/None: NEVER for last-access style fields, UNKNOWN for creation dates.
    """
    if value in (None, "", 0):
        return missing
    if isinstance(value, int | float) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=UTC).date().isoformat()
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return display(text)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def contains_text(value: Any, needle: str) -> bool:
    """Case-insensitive substring match; an empty needle matches everything."""
    normalized = needle.strip().casefold()
    return not normalized or normalized in str(value or "").casefold()


def format_rows(
    items: Sequence[Any],
    render: Callable[[Any], str],
    empty_message: str,
    limit: int = MAX_ROWS,
) -> str:
    if not items:
        return empty_message
    lines: Iterable[str] = (render(item) for item in items[:limit])
    text = "\n".join(lines)
    hidden = len(items) - limit
    return f"{text}\n…and {hidden} more" if hidden > 0 else text


def format_listing(items: Sequence[Any], total: int, noun: str, render: Callable[[Any], str]) -> str:
    """'N of T <noun>:' plus capped rows, or a no-match line that still states the total."""
    if not items:
        return f"No {noun} match (out of {total})."
    return f"{len(items)} of {total} {noun}:\n{format_rows(items, render, empty_message='')}"
