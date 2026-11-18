# Getting started

Run the example server on your laptop and use it from Claude Code, in about 5 minutes.

## What you need

| | Required? | Why |
|---|---|---|
| [uv](https://docs.astral.sh/uv/getting-started/installation/) (`brew install uv`) | ✅ | Runs the project (installs Python 3.12 by itself) |
| [Claude Code](https://claude.com/claude-code) or another MCP client | ✅ | The AI you talk to |
| An AI provider key (e.g. OpenAI) | Optional | Only for `search_docs`, the test agent and the evals |

## 1. Install and test

```bash
uv sync
uv run pytest
```

## 2. Connect it to Claude Code

From inside the repo folder:

```bash
claude mcp add --scope user example-mcp -- uv --directory "$PWD" run example-mcp
```

Open Claude Code, type `/mcp`, and check that `example-mcp` is connected. Then ask:

- *"Which company does Clementine Bauch work for?"*
- *"How many open todos does user 1 have?"*
- *"How many posts mention 'nesciunt'?"*
- *"What's Ervin Howell's phone number?"* (it should say that's not available)

Claude may ask permission the first time it uses a tool. That's normal.

## 3. Optional: docs search

```bash
cp .env.example .env          # then set OPENAI_API_KEY
uv run python -m ingest.ingest_docs
```

Restart Claude Code, then ask *"How do I paginate results in the example API?"*. Without a key or an index,
everything else still works; only `search_docs` says it's unavailable and why.

## 4. Optional: write tools

Set `ENABLE_WRITE_TOOLS=true` and `WRITE_ALLOWED_IDS=1` in `.env`, restart, and ask *"Mark todo 1 as
completed"*. Claude Code asks before running it. The example API answers but doesn't store the change.

## 5. Optional: HTTP mode (MCP Inspector, other clients)

```bash
uv run example-mcp --http            # serves http://127.0.0.1:8000/mcp
npx @modelcontextprotocol/inspector  # connect with transport "Streamable HTTP" and that URL
```

It only binds to `127.0.0.1`, `localhost` or `::1`, because it has no auth yet.

## Troubleshooting

| You see | What it means | What to do |
|---|---|---|
| `example-mcp` not in `/mcp` | Not registered, or wrong folder | Re-run step 2 from inside the repo folder |
| "The API failed or is unreachable" | No internet, or `API_BASE_URL` is wrong | Check `uv run python scripts/probe.py users` |
| "API_TOKEN ... rejected" | The API needs a different token | Fix `API_TOKEN` in `.env`, restart |
| "search_docs is disabled" | No provider key or index | Step 3, or ignore it |
| `MCP_HOST: must be one of ...` | Non-loopback host in `.env` | Use `127.0.0.1` until the server has OAuth |
| A change to `.env` isn't picked up | The server reads `.env` at start | Restart Claude Code |
| `ERROR Error in standalone SSE ... ClosedResourceError` in `--http` mode | The MCP SDK (1.x) logs this when a client disconnects | Harmless; the session ended normally |
