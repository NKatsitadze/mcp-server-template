# CLAUDE.md: example-mcp

An MCP server that exposes an HTTP API as a few safe, read-first tools. Why each rule exists: docs/PATTERNS.md.

## Layout
- `src/example_mcp/settings.py` loads env config and validates it. Never echo input values in errors.
  `load_env_file()` exports `.env` for provider SDKs; call it in every entry point.
- `log.py` logs to stderr only, with a redaction filter. **Never `print()` in `src/`**: stdout is the MCP stdio stream.
- `errors.py` holds the error types plus `run_backend()` / `run_write()`, which turn them into `ToolError`
  messages the model can act on.
- `auth.py` holds token sources. `client.py` (`ApiClient.get/post/patch`) is the only place that does HTTP.
- `formatting/<domain>.py` holds pure functions from raw API data to short text, built from field allowlists.
- `tools/<domain>.py` exposes `register(mcp, client)`. Tools call `run_backend(client.get(...))`, then a formatter.
- `server.py` has `create_server(...)` (pure wiring) and `main()`. The transport is the `--http` flag, never an env var.

## Rules
- **Expose few tools.** Each tool must answer real questions. Prefer filter arguments over more tools.
- New tools are read-only with `READ_ONLY` annotations and `structured_output=False`. Write tools need
  `destructiveHint=True`, an entry in `WRITE_TOOL_NAMES`, the `WRITE_ALLOWED_IDS` guard, `run_write`, and approval.
- Tool docstrings say when to use the tool and which tool provides the ids it needs. Not-found errors name that tool.
- Formatters use an allowlist of fields. Never return tokens, keys, cookies or personal data. Add a no-leak test.
- Read the real response shape (`scripts/probe.py <path>`) before writing a formatter.
- Every module has tests. HTTP is mocked with `respx` or `tests/conftest.py:FakeClient`; nothing hits the network.
- Don't close shared clients in a FastMCP lifespan (it runs per session over HTTP); `serve()` owns them.
- No hardcoded machine paths: build them from `Path(__file__)` or env vars.
- Keep files small and single-purpose, and type everything.

## Commands
`uv run pytest` · `uv run ruff check . && uv run ruff format --check .` · `uv run python scripts/probe.py users`
· `uv run python -m ingest.ingest_docs` · `uv run python -m evals.run_evals --runs 3`
