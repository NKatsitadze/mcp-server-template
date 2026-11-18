# Todos resource (/todos)

`GET /todos` returns all 200 todos, 20 per user. `GET /todos/{id}` returns one todo; an unknown id
returns HTTP 404 with `{}`.

## Fields

| Field | Type | Notes |
|---|---|---|
| `id` | integer | 1 to 200 |
| `userId` | integer | the owner, see `/users` |
| `title` | string | short text |
| `completed` | boolean | `true` when done, `false` when open |

## Filtering

Filter by any field with a query parameter:

- `GET /todos?userId=1`: user 1's todos
- `GET /todos?completed=false`: open todos only
- `GET /todos?userId=1&completed=false`: user 1's open todos

A filter value that matches nothing (for example `userId=99`) returns an empty array `[]` with
HTTP 200, not a 404. That is why the `list_todos` tool says "call list_users to get valid ids" when a
user filter returns nothing.

## Completing a todo

`PATCH /todos/{id}` with the body `{"completed": true}` marks a todo as completed. The API answers
with the updated todo, but does not store the change (see the writes page). The MCP tool
`complete_todo(todo_id)` does this; it is off unless `ENABLE_WRITE_TOOLS=true`, asks for approval,
and does nothing when the todo is already completed.

## MCP tools

- `list_todos(user_id, completed)`: counts of open and completed todos, then up to 50 rows.
