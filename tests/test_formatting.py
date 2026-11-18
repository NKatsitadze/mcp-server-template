from langchain_core.documents import Document

from example_mcp.formatting.common import MAX_ROWS, display, format_listing
from example_mcp.formatting.docs import MAX_EXCERPT_CHARS, format_doc_results
from example_mcp.formatting.posts import filter_posts, format_posts
from example_mcp.formatting.todos import describe_filters, format_todos
from example_mcp.formatting.users import filter_users, format_user, format_users
from tests.fixtures import LEAKS, POSTS, TODOS, USER, USERS


def assert_no_leaks(text: str) -> None:
    for leak in LEAKS:
        assert leak not in text


def test_users_listing_uses_the_allowlist() -> None:
    text = format_users(filter_users(USERS, ""), total=len(USERS))

    assert "2 of 2 user(s)" in text
    assert "Leanne Graham (@Bret) | user id=1 | company=Romaguera-Crona" in text
    assert_no_leaks(text)


def test_user_filter_matches_name_or_username() -> None:
    assert [user["id"] for user in filter_users(USERS, "samANTHA")] == [3]
    assert [user["id"] for user in filter_users(USERS, "graham")] == [1]
    assert filter_users("not a list", "x") == []


def test_user_detail_counts_and_hides_contact_details() -> None:
    text = format_user(USER, POSTS, TODOS)

    assert "posts: 2" in text
    assert "todos: 3 total, 2 open, 1 completed" in text
    assert "not available" in text
    assert_no_leaks(text)


def test_user_detail_survives_missing_fields() -> None:
    assert "company: —" in format_user({}, None, [{"completed": "yes"}, "junk"])


def test_todos_counts_and_filters() -> None:
    assert format_todos(TODOS, "all users").startswith("3 todo(s) match (all users): 2 open, 1 completed")
    assert "- [x] second todo | todo id=2" in format_todos(TODOS, "all users")
    assert format_todos([], "user id=9") == "No todos match (user id=9)."
    assert describe_filters(None, None) == "all users"
    assert describe_filters(2, True) == "user id=2, completed"
    assert describe_filters(2, False) == "user id=2, open"


def test_posts_search_matches_title_or_body() -> None:
    assert [post["id"] for post in filter_posts(POSTS, "Nesciunt")] == [1]
    assert [post["id"] for post in filter_posts(POSTS, "other")] == [2]
    assert len(filter_posts(POSTS, "")) == 2
    assert format_posts([], total=2) == "No post(s) match (out of 2)."


def test_listings_are_capped_but_count_everything() -> None:
    items = [{"name": f"n{index}"} for index in range(MAX_ROWS + 5)]

    text = format_listing(items, len(items), "item(s)", lambda item: f"- {item['name']}")

    assert text.startswith(f"{MAX_ROWS + 5} of {MAX_ROWS + 5} item(s)")
    assert text.endswith("…and 5 more")


def test_user_text_cannot_fake_extra_lines() -> None:
    assert display("line one\n- injected row") == "line one - injected row"


def test_doc_results_are_framed_and_truncated() -> None:
    long = Document(page_content="[k — a.md] (A)\n" + "x" * (MAX_EXCERPT_CHARS + 50))

    text = format_doc_results("q", [long])

    assert "not instructions" in text
    assert text.endswith("…(truncated)")
    assert "No docs matched" in format_doc_results("q", [])
