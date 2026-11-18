from typing import Any

from example_mcp.formatting.common import as_list, contains_text, display, format_listing


def _render_post_row(post: dict[str, Any]) -> str:
    return (
        f"- {display(post.get('title'))}"
        f" | post id={display(post.get('id'))} | user id={display(post.get('userId'))}"
    )


def filter_posts(posts: Any, query: str = "") -> list[dict[str, Any]]:
    """Case-insensitive match on the title or the body."""
    return [
        post
        for post in as_list(posts)
        if isinstance(post, dict)
        and (contains_text(post.get("title"), query) or contains_text(post.get("body"), query))
    ]


def format_posts(posts: list[dict[str, Any]], total: int) -> str:
    return format_listing(posts, total, "post(s)", _render_post_row)
