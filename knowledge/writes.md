# Writes: POST, PUT, PATCH and DELETE

The API accepts writes but never stores them. It answers as if the write had happened:

| Request | Status | Response |
|---|---|---|
| `POST /posts` with `title`, `body`, `userId` | 201 | the sent fields plus `id: 101` |
| `PATCH /todos/1` with `{"completed": true}` | 200 | todo 1 with `completed: true` |
| `PUT /posts/1` with a full post | 200 | the sent post |
| `PUT /posts/999` (unknown id) | 404 | `{}` |
| `DELETE /posts/1` | 200 | `{}` |

A later `GET` still shows the original data. For example, after `PATCH /todos/1`, `GET /todos/1`
still has `completed: false`.

## Safety rules for write tools in this server

1. Write tools are off unless `ENABLE_WRITE_TOOLS=true`.
2. They are annotated `destructiveHint`, so clients such as Claude Code ask before each call.
3. `WRITE_ALLOWED_IDS` limits which ids may be changed; any other id is refused before the API is
   called.
4. A failed or timed-out write is reported as "may or may not have been applied, do not retry".
5. With a real API, re-read the item after the write and report that state, not the API's echo.
