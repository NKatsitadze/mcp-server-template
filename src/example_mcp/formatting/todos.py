from typing import Any

from example_mcp.formatting.common import as_list, display, format_rows


def _render_todo_row(todo: dict[str, Any]) -> str:
    mark = "x" if todo.get("completed") is True else " "
    return (
        f"- [{mark}] {display(todo.get('title'))}"
        f" | todo id={display(todo.get('id'))} | user id={display(todo.get('userId'))}"
    )


def format_todos(todos: Any, filters: str) -> str:
    """Counts first (the model usually needs them), then the capped rows."""
    items = [todo for todo in as_list(todos) if isinstance(todo, dict)]
    if not items:
        return f"No todos match ({filters})."
    done = sum(1 for todo in items if todo.get("completed") is True)
    header = f"{len(items)} todo(s) match ({filters}): {len(items) - done} open, {done} completed"
    return f"{header}\n{format_rows(items, _render_todo_row, empty_message='')}"


def describe_filters(user_id: int | None, completed: bool | None) -> str:
    parts = [f"user id={user_id}" if user_id is not None else "all users"]
    if completed is not None:
        parts.append("completed" if completed else "open")
    return ", ".join(parts)
