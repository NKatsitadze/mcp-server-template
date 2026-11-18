# Patterns: what this template does, and why

Every rule here was learned the hard way while building a production MCP server over a real dashboard
API. Each one has the problem it prevents. Read this before removing any of them.

## Server and transport

**Log to stderr only; never `print()` in `src/`.**
In stdio mode, stdout *is* the JSON-RPC stream. One stray `print()`, or a library that prints a banner on
import, corrupts it, and the client just shows "disconnected". `tests/test_stdio_e2e.py` starts the real
server and talks MCP to it, which catches this; unit tests can't.

**`create_server()` is pure wiring; `main()` does the I/O.**
Tests build a server around a fake client and call tools with `server.call_tool(...)`. No network, no env.

**Don't close shared clients in the FastMCP lifespan.**
Over Streamable HTTP, FastMCP (mcp 1.x) enters the lifespan **once per client session**. A client closed
there works for the first session and is dead for every later one. `serve()` opens and closes the client
around the transport, in the same event loop (an httpx client can't be closed after its loop ended).

**The transport is a command-line flag, not an env var.**
`.env` is read by every launch, including the stdio launches of Claude Code and the test agent. An
`MCP_TRANSPORT=http` line there would make them start an HTTP server and hang.

**HTTP binds to loopback only until there is auth.**
FastMCP turns on DNS-rebinding protection only for exactly `127.0.0.1`, `localhost` and `::1`. Any other host
(even `127.0.0.2`) serves the tools unprotected and unauthenticated, so settings refuse it. For a hosted server
use OAuth 2.1 (see "Later: hosting" below).

## Talking to the backend

**One client class does all HTTP (`client.py`).**
Tools never see httpx. Changing auth, base URLs or the transport (e.g. a monolith migration) touches one file.

**Map HTTP status to typed errors, then to messages the model can act on (`errors.py`).**
- 404 → "Not found. Call `list_users` to get valid ids." Naming the tool that lists valid ids turns a dead end
  into a retry with a real id.
- 401 → fix the token in `.env` (the model can't, so it tells the user). 403 → "lacks rights".
- 5xx / timeout → "try again later" for reads, but "may or may not have been applied, **do not retry**" for
  writes. A retried non-idempotent write (e.g. "rotate a key") does it twice.

**Retry a 401 once, and only if the credentials can be refreshed.** Never retry a 403, a 5xx or a write.

**Recipe: a login-based token source** (for dashboards with email + password sessions):
1. One `asyncio.Lock` around login, so parallel tool calls trigger one login, not five.
2. **Never retry a failed login.** Accounts lock after a few wrong passwords; a retry loop locks the account
   by itself. Raise an error that says "fix .env and restart", and keep failing until restart.
3. Keep the session alive before its idle timeout (a cheap "activity" call when it's been idle a while).
4. On a 401, invalidate *that* token (compare it, so two parallel 401s don't log in twice) and log in again
   once. If the fresh token is rejected too, stop: it's a rights problem, not an expiry.
5. Check the account has no 2FA and isn't on "first login" or "password expired".

**Read the real response shape before writing a formatter.** `scripts/probe.py <path>` prints keys and types,
never values. Real APIs differ from their docs; formatters built on guesses show "—" everywhere.

**Some APIs return `[]` instead of 404** for unknown ids in filters (`/todos?userId=99`). Fetch the parent
first (`/users/99` gives a real 404), or add a hint to the empty result.

## Tool design

**Expose few tools, each answering real questions.** Filters (`name_contains`, `completed`) beat more tools.
Every extra tool costs tokens on every request and gives the model more ways to pick wrong.

**Tool output is short text for the model, built from an allowlist of fields.**
- An allowlist means a new field the API adds is ignored until someone adds it on purpose. A denylist leaks it.
- Never return tokens, keys, cookies or personal data (the example hides email, phone and address). The AI's
  answer is shown in the client's app; once a value is in tool output, you can't control where it goes.
- Every user-facing tool has a no-leak test.

**Cap lists but always give the count.** "12 of 100 post(s)" plus at most 50 rows plus "…and N more". The
model then says "partial" or narrows the filter instead of claiming the rows are everything.

**Flatten user-entered text** (`display()`): newlines become spaces and long text is cut, so a title can't
fake extra rows or bury the output. Tell the model that names and titles are data, never instructions.

**Validate arguments in the signature** (`Field(ge=1)`), so bad ids are refused before any API call.

**Add data-driven notes when a number could be misread.** For example, when per-reason counts add up to more
than the total because one item can have several reasons, say so in the output.

## Write tools

Off unless `ENABLE_WRITE_TOOLS=true`. The layers, in the order a call meets them:
1. **The client asks.** `destructiveHint=True` makes Claude Code ask before each call. The test agent pauses
   with `HumanInTheLoopMiddleware`; evals reject every write automatically.
2. **The server checks an allowlist** (`WRITE_ALLOWED_IDS`), right next to the action. A prompt can't talk
   its way past code.
3. **Read first.** Skip the write when nothing would change (already completed).
4. **Errors are write-safe** (`run_write`): unknown outcome → "do not retry".
5. **Verify by re-reading** after the write and report before/after. (The example API doesn't store writes,
   so the template reports the API's answer instead and says so.)

Every write tool goes into `WRITE_TOOL_NAMES`; the agent's approval gates and the eval checks use that list.

## Docs search (RAG)

**Hybrid search: vectors + BM25, merged with reciprocal rank fusion.** Vectors find meaning; BM25 finds exact
names (`userId`, `invalid-params`) that embeddings blur. RRF merges by rank, so the scores never need the same
scale.

**Put the facts people ask about into every chunk's header** (citation, title, key names, error codes). A long
chunk that lost them to splitting still carries them. Separate "summary card" documents were tried: they won
the top slots and pushed out the chunks with the answer.

**Measure top-k on your corpus** with the questions the AI actually sends (agents send keyword-ish queries,
not polished sentences). Find the rank of the first chunk with the answer; keep a slot or two of slack.

**Know the small-corpus weak spot.** In a corpus of a few dozen chunks, common words ("user", "fields") appear
in so many chunks that BM25 scores them near zero, and rank fusion puts a chunk that only one ranker finds
(even at rank 1) behind chunks both find. Measured on this template's 18 chunks: the users fields table was
vector rank 1 but fused rank 9. Section headings in chunk headers and a plain sentence next to a table help
vector search; real fixes (a reranker, or weighting by corpus size) belong to a real corpus, not to tuning
on a toy one.

**Fail closed on secrets before embedding** (`ingest/secret_gate.py`). Chunk text goes to the embeddings
provider and is stored on disk. A file that looks like it holds a credential is skipped whole and only its
path and pattern names are printed. Expect false positives on fake fixtures; that's fine. Redaction alone
isn't enough: it misses field names you didn't think of.

**Embed everything first, then replace the collection.** Resetting first leaves a half-empty index when the
provider fails mid-run. Stable chunk ids make re-runs idempotent.

**Recipe: indexing another repository.** Clone only what you need, with a fresh temp clone swapped in on
success: `git clone --filter=blob:none --no-checkout --depth 1 -b <branch> <url> tmp`, then
`git sparse-checkout set --no-cone '/src/' '/docs/'` (anchored patterns), `git checkout`. Never check out
config files, scripts or test fixtures that may hold credentials or realistic personal data, and never pull
in someone's working copy. Point a `LocalSource` at the checkout.

**Index the facts the tools can't give.** The docs tool says it is documentation, not live data, and cites
`[source — file]`; the other tools give live values.

## Test agent and evals

**One persistent MCP session per agent run.** `client.get_tools()` starts a new server process (and a new
backend login) for every tool call. `open_agent()` opens one session for the whole run.

**Evals check behaviour, not just answers.** Each case can check: tools called, arguments (subset match),
forbidden tools, call budget, answer text, and an LLM-judge criterion. Global rules apply to every case: no
write unless the case asks for one, every write went through approval, a rejected write is never retried.

**Check tool calls on every data case.** Models know public datasets (and sometimes your docs) from training.
A right answer without the right tool call is a lucky guess.

**Use the judge for meaning and counts, keywords for exact values.** Keyword lists break on every new
phrasing ("didn't find any", ": 0"), and substrings lie ("9" is in "19"). Keep `must_contain_any` for ids,
names and codes.

**Calibrate the judge before trusting it.** `evals/judge_calibration.yaml` holds human-labeled answers (right
ones in different phrasings, realistic wrong ones). The judge must agree with every label on every run.
A cheaper judge model scored 77/85 in one project (it confused two look-alike ids); the next size up scored 85/85.
When the judge misgrades a real answer, add it to the labels.

**Normalize curly quotes before comparing text.** Models write `can’t`; in one project, 6 of 7 "failures"
were checker bugs like this, not model errors. Read the failing answers before changing prompts or tools.

**Fail the run when any case fails every attempt**, not only below the threshold: one broken behaviour can
hide inside a good average.

**Pin model snapshots and record the prompt version** in reports, so scores compare across runs. Re-run evals
before releases, when backend data changes and when a new model ships; not on every commit (they cost money).

**Expected values are a data snapshot.** When live data changes, check the real value with the tools first,
then update the case.

## Later: hosting

What a hosted (remote) version needs, from the MCP spec and from how established vendors ship theirs:
- Streamable HTTP behind HTTPS; the protocol is stateless, so it scales horizontally.
- **OAuth 2.1** with the MCP server as a *resource server*: publish Protected Resource Metadata (RFC 9728),
  clients use PKCE and the `resource` parameter, Client ID Metadata Documents preferred over Dynamic Client
  Registration.
- **No token passthrough.** Accept only tokens issued for this server (audience check) and never forward them
  to the backend; exchange them for a backend session for that user.
- Restrict in layers: an org/role permission to use the MCP, scopes on a consent screen (read-only first),
  tools filtered by the user's rights, and the backend's own checks on every call.
- Sentry for errors, an audit event per tool call, a per-user rate limit.
- One deployment per environment, each with its own keys and docs index.
