# Example API overview

The example API is JSONPlaceholder, a free public fake REST API at
`https://jsonplaceholder.typicode.com`. This template's MCP server uses it as its backend so every
tool, test and eval works without an account.

## Authentication

None. Requests need no API key and no `Authorization` header. When you replace the example with a
real API that needs a key, set `API_TOKEN` in `.env`: the client then sends `Authorization: Bearer <token>`
on every request.

## Resources

| Resource | Endpoint | Count | Per parent |
|---|---|---|---|
| users | `/users` | 10 | |
| posts | `/posts` | 100 | 10 per user |
| comments | `/comments` | 500 | 5 per post |
| albums | `/albums` | 100 | 10 per user |
| photos | `/photos` | 5000 | 50 per album |
| todos | `/todos` | 200 | 20 per user |

The data is fixed: it never changes, and writes are not stored (see the writes page).

## Formats

Every response body is JSON. Ids are integers starting at 1. A single item is returned as an object,
a collection as an array.
