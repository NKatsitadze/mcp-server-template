# Errors and status codes

| Situation | Status | Body |
|---|---|---|
| unknown id, e.g. `GET /users/99` | 404 | `{}` |
| unknown route, e.g. `GET /nothing` | 404 | `{}` |
| filter that matches nothing, e.g. `GET /todos?userId=abc` | 200 | `[]` |
| successful read | 200 | the object or array |
| created with `POST` | 201 | the new object with `id` 101 |

## How the MCP server maps errors

The client (`client.py`) turns HTTP status codes into error types, and `errors.py` turns those into
messages that tell the model what to do next:

- 404: "Not found. Call list_users to get valid ids." (the tool that lists valid ids is named)
- 401: the API rejected `API_TOKEN`; the user must fix `.env` and restart
- 403: the account lacks rights
- other 4xx: the API rejected the request, with its error code when the body has one
- 5xx, timeouts and network failures: the API failed or is unreachable; for a write, "may or may
  not have been applied, do not retry"

A 401 is retried once only when the credentials can be refreshed. The example's static token can't,
so nothing is retried.
