# Posts resource (/posts)

`GET /posts` returns all 100 posts, 10 per user. `GET /posts/{id}` returns one post; an unknown id
returns HTTP 404 with `{}`.

## Fields

| Field | Type | Notes |
|---|---|---|
| `id` | integer | 1 to 100 |
| `userId` | integer | the author, see `/users` |
| `title` | string | Latin placeholder text |
| `body` | string | Latin placeholder text, several lines |

## Filtering and nested routes

- `GET /posts?userId=3`: the 10 posts of user 3
- `GET /posts/{id}/comments`: the 5 comments of a post (same as `/comments?postId={id}`)

The API has no full-text search. The `search_posts` tool fetches the posts (all of them, or one
user's) and matches the query against the title and body itself, case-insensitive.

## MCP tools

- `search_posts(query, user_id)`: matching posts with their post id and user id, a match count,
  and at most 50 rows.
