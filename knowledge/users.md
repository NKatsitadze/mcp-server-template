# Users resource (/users)

`GET /users` returns all 10 users. `GET /users/{id}` returns one user; an unknown id returns
HTTP 404 with an empty object `{}`.

## Fields

A user has these fields: id, name, username, email, phone, website, address and company.

| Field | Type | Notes |
|---|---|---|
| `id` | integer | 1 to 10 |
| `name` | string | full name, e.g. "Leanne Graham" |
| `username` | string | e.g. "Bret" |
| `email` | string | contact detail: never returned by the MCP tools |
| `phone` | string | contact detail: never returned by the MCP tools |
| `website` | string | not returned by the MCP tools |
| `address` | object | `street`, `suite`, `city`, `zipcode`, `geo` (`lat`, `lng`); never returned |
| `company` | object | `name`, `catchPhrase`, `bs`; the MCP tools return only `company.name` |

## Why some fields are hidden

The MCP server picks fields with an allowlist (`formatting/users.py`). Contact details and the home
address are personal data, so the model never sees them, and no prompt can make the server return
them. A new field added by the API is ignored until someone adds it to the allowlist on purpose.

## Nested routes

- `GET /users/{id}/posts`: the user's posts (same as `/posts?userId={id}`)
- `GET /users/{id}/todos`: the user's todos (same as `/todos?userId={id}`)
- `GET /users/{id}/albums`: the user's albums

## MCP tools

- `list_users(name_contains)`: matches the full name or the username, case-insensitive.
- `get_user(user_id)`: the profile plus the user's number of posts and open and completed todos.
