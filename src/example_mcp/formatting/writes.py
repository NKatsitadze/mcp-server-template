from typing import Any

from example_mcp.formatting.common import as_dict, display


def is_completed(todo: Any) -> bool:
    return as_dict(todo).get("completed") is True


def format_already_completed(todo: Any) -> str:
    details = as_dict(todo)
    return (
        f"Todo {display(details.get('id'))} ({display(details.get('title'))}) is already completed. "
        "Nothing was changed."
    )


def format_complete_result(before: Any, response: Any) -> str:
    """Report the state before and what the API answered. With a real API, re-read the item after the
    write and report that instead: the example API echoes the change but never stores it."""
    old, new = as_dict(before), as_dict(response)
    return (
        f"Todo {display(old.get('id'))} ({display(old.get('title'))})\n"
        f"before: completed={display(is_completed(old))}\n"
        f"API response: completed={display(is_completed(new))}\n"
        "Note: the example API does not persist writes, so a later read still shows the old state."
    )
