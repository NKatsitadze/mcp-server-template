# Comments resource (/comments)

`GET /comments` returns all 500 comments, 5 per post.

## Fields

| Field | Type | Notes |
|---|---|---|
| `id` | integer | 1 to 500 |
| `postId` | integer | the post it belongs to |
| `name` | string | comment title |
| `email` | string | the commenter's email address (personal data) |
| `body` | string | comment text |

## Filtering

- `GET /comments?postId=1`: the comments of post 1
- `GET /posts/1/comments`: the same, as a nested route

## MCP tools

None yet. A comments tool would follow the same rules as the others: an allowlist of fields that
leaves out `email`, a capped list, and a not-found hint that names the tool that lists valid ids.
