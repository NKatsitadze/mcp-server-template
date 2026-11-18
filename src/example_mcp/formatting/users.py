"""Users of the example API.

Field allowlist: name, username, id and company name only. The API also returns email, phone and a
home address; they are never read here, so they can never reach the model (see the no-leak tests).
"""

from typing import Any

from example_mcp.formatting.common import as_dict, as_list, contains_text, display, format_listing


def company_name(user: dict[str, Any]) -> Any:
    return as_dict(user.get("company")).get("name")


def _render_user_row(user: dict[str, Any]) -> str:
    return (
        f"- {display(user.get('name'))} (@{display(user.get('username'))})"
        f" | user id={display(user.get('id'))} | company={display(company_name(user))}"
    )


def filter_users(users: Any, name_contains: str = "") -> list[dict[str, Any]]:
    """Matches the full name or the username."""
    return [
        user
        for user in as_list(users)
        if isinstance(user, dict)
        and (
            contains_text(user.get("name"), name_contains)
            or contains_text(user.get("username"), name_contains)
        )
    ]


def format_users(users: list[dict[str, Any]], total: int) -> str:
    return format_listing(users, total, "user(s)", _render_user_row)


def format_user(user: Any, posts: Any, todos: Any) -> str:
    details = as_dict(user)
    todo_items = [todo for todo in as_list(todos) if isinstance(todo, dict)]
    done = sum(1 for todo in todo_items if todo.get("completed") is True)
    return (
        f"User {display(details.get('name'))} (@{display(details.get('username'))}, "
        f"user id={display(details.get('id'))})\n"
        f"company: {display(company_name(details))}\n"
        f"posts: {len(as_list(posts))}\n"
        f"todos: {len(todo_items)} total, {len(todo_items) - done} open, {done} completed\n"
        "(contact details and address are not available through this server)"
    )
