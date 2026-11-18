# mcp-server-template

A starter for MCP servers that expose an HTTP API to AI assistants (Claude Code, Claude Desktop, Cursor,
LangGraph agents) as a few **safe, read-first tools**. It works out of the box against a free public
fake API (JSONPlaceholder), with:

- a typed client, errors the model can act on, and stdout-safe logging;
- tools built from **field allowlists**, with no-leak tests;
- **approval-gated write tools** (off by default);
- **docs search** (hybrid RAG with a secret gate);
- a **test agent with evals** and a **calibrated LLM judge**;
- an end-to-end stdio test and CI.

Why every piece exists: [docs/PATTERNS.md](docs/PATTERNS.md). Connecting it to Claude Code:
[GETTING_STARTED.md](GETTING_STARTED.md).

> Versions (2026-11): Python 3.12, `mcp>=1.30,<2` (held below 2 because `langchain-mcp-adapters` doesn't
> support it yet), langchain 1.4, uv 0.12. The MCP spec and SDKs move fast; check them when you start.

## Start a new server from this template

```bash
uv run python scripts/new_project.py weather-mcp            # creates ../weather-mcp
cd ../weather-mcp && git init -b main && uv sync && uv run pytest
```

It copies everything except local state (`.git`, `.venv`, `.env`, `data/`, eval reports), renames the package
(`example_mcp` → `weather_mcp`), the command and server name (`example-mcp` → `weather-mcp`), and refreshes
`uv.lock`. On GitHub, "Use this template" works too; then rename by hand. The script and its test exist only
in the template.

## Quick start

```bash
uv sync
uv run pytest                                  # unit tests + stdio end-to-end test, no network needed
uv run python scripts/probe.py users           # live, read-only: prints the response SHAPE only
npx @modelcontextprotocol/inspector uv --directory "$PWD" run example-mcp      # try the tools
```

The server needs no `.env` for the example API. For the agent, evals and docs search:
`cp .env.example .env`, then set `OPENAI_API_KEY` (or another provider's key) and `MODEL`.

## Layout

```
src/example_mcp/
  settings.py      env config, validation, load_env_file()
  log.py           stderr-only logging with redaction
  errors.py        typed errors -> ToolError messages (run_backend, run_write)
  auth.py          token sources (NoAuth, StaticToken)
  client.py        ApiClient.get/post/patch: the only place that does HTTP
  formatting/      pure functions: raw API data -> short text, from field allowlists
  tools/           one module per domain, register(mcp, client)
  docs/            hybrid search (Chroma + BM25 + rank fusion)
  server.py        create_server() wiring, serve(), main() (--http flag)
agent/             test agent (LangChain create_agent over one MCP session)
evals/             questions.yaml, checks, LLM judge + calibration, runner
ingest/            builds the docs index from knowledge/ (secret gate, safe rebuild)
knowledge/         the docs the search indexes (here: the example API)
scripts/           probe.py, new_project.py
tests/             everything mocked; test_stdio_e2e.py starts the real server
docs/PATTERNS.md   the rules and the reasons behind them
```

## Add a tool in 5 steps

1. **Read the real shape:** `uv run python scripts/probe.py <path>`.
2. **Formatter** in `formatting/<domain>.py`: pure function, allowlist of fields, `display()` for user text,
   `format_listing()` for capped lists with counts.
3. **Tool** in `tools/<domain>.py`: `@mcp.tool(annotations=READ_ONLY, structured_output=False)`, a docstring
   that says when to use it and where its ids come from, `run_backend(client.get(...), hint_tool=...)`.
4. **Register** the module in `server.py` (`TOOL_MODULES`) and mention it in `INSTRUCTIONS`.
5. **Test** it in the `TOOL_CASES` table in `tests/test_server.py` (request, output, no leaks), then add an
   eval case in `evals/questions.yaml`.

## Replace the example API

1. Set `API_BASE_URL` (and `API_TOKEN` if it needs a bearer token) in `.env`. For login-based APIs, write a
   token source following the recipe in PATTERNS.md.
2. Replace `tools/users.py`, `todos.py`, `posts.py` and their formatters, tests and fixtures.
3. Replace `knowledge/` with your docs and re-run the ingest; rewrite `evals/questions.yaml` and the judge
   labels for your data; update `INSTRUCTIONS` and `agent/prompt.py`.

## Tools (example)

| Tool | API | Notes |
|---|---|---|
| `list_users(name_contains?)` | `GET /users` | name, username, id, company; never email, phone or address |
| `get_user(user_id)` | `GET /users/{id}`, `/posts`, `/todos` | profile + post and todo counts; 404 hints `list_users` |
| `list_todos(user_id?, completed?)` | `GET /todos` | open/completed counts, up to 50 rows |
| `search_posts(query?, user_id?)` | `GET /posts` | local title/body match with a match count |
| `search_docs(query)` | local index | cited excerpts from `knowledge/` |
| `complete_todo(todo_id)` ✏️ | `PATCH /todos/{id}` | write: off by default, allowlist, approval; the API doesn't persist it |

## Optional parts (delete what you don't need)

| Part | Delete | Then |
|---|---|---|
| Write tools | `tools/writes.py`, `formatting/writes.py`, `tests/test_writes.py` | remove `writes` from `server.py`; replace the `WRITE_TOOL_NAMES` imports in `agent/factory.py` and `evals/checks.py` with `()` |
| Docs search | `docs/`, `tools/docs.py`, `formatting/docs.py`, `ingest/`, `knowledge/`, their tests | remove `DocsSearch` from `server.py`; drop `langchain-chroma`, `rank-bm25`, `langchain-text-splitters` |
| Agent + evals | `agent/`, `evals/`, their tests | drop the `agent` dependency group |
| HTTP transport | the `--http` flag in `server.py` | keep stdio only |

## Docs search

```bash
uv run python -m ingest.ingest_docs     # embeds knowledge/ into data/chroma; re-run when docs change
```

- Every file passes the **secret gate** before embedding; a flagged file is skipped whole and only its path
  and pattern names are printed. The collection is replaced only after all embeddings succeed.
- `EMBEDDING_MODEL` is a `provider:model` string (default `openai:text-embedding-3-small`) and must match
  between ingest and server. LangChain's `init_embeddings` has no Anthropic provider: with Claude models, still
  use another provider's key for embeddings.
- `RESULTS = 4` in `docs/search.py`: re-measure it on your corpus (PATTERNS.md).

## Test agent and evals

```bash
uv run python -m agent.chat "how many open todos does user 1 have?"   # one question, prints tool calls
uv run python -m evals.calibrate_judge --runs 3                        # judge must agree with every label
uv run python -m evals.run_evals --runs 3                              # all cases x 3
```

- `MODEL` and `JUDGE_MODEL` are `provider:model` strings for `init_chat_model`
  (e.g. `anthropic:claude-sonnet-5-5` after `uv add langchain-anthropic`). The default judge is an OpenAI model,
  so calibrate again when you change it.
- The runner exits 1 below 90% **or** when any case failed every run. Reports with every answer go to
  `evals/results/` (gitignored). Read the answers before changing anything.
- Evals switch the write tools on for the server they start and reject every write proposal, so nothing changes.
- `LANGSMITH_TRACING=true` plus `LANGSMITH_API_KEY` traces every run.

## Roadmap (for servers built from this)

- Hosting: Streamable HTTP behind HTTPS with OAuth 2.1 (see PATTERNS.md "Later: hosting"), Docker, Sentry,
  audit events, per-user rate limits.
- CI: run a read-only contract check against a dev API after backend deploys (are the fields formatters rely
  on still there?), and rebuild the docs index when its sources change.
- Upgrade to `mcp` 2.x once `langchain-mcp-adapters` supports it.

## License

MIT
