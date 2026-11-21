# EGM over MCP

`egm mcp` serves a knowledge base to any MCP client (Claude Desktop, Claude Code, or your own
agent) over stdio. It needs nothing beyond the kit: no web server, no extra packages.

    egm mcp /abs/path/kb.vtx                  # read-only (default)
    egm mcp /abs/path/kb.vtx --writable       # also lets the model add evidence
    egm mcp /abs/path/facts.txt               # a facts file works too; it is ingested at start

The knowledge base loads and builds its inferences once at startup. After that, each tool call
is a sub-millisecond lookup.

## Connecting a client

**Claude Code:**

    claude mcp add egm -- egm mcp /abs/path/kb.vtx

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "egm": { "command": "egm", "args": ["mcp", "/abs/path/kb.vtx"] }
  }
}
```

Use absolute paths. If `egm` isn't on the client's PATH, give its full path as `command`
(`which egm` shows it), or use `"command": "python3", "args": ["-m", "egm.cli", "mcp", ...]`
from the environment you installed into.

## Tools

Read-only, always available:

| Tool | Use |
|---|---|
| `egm_relations` | What can be asked: learned relations, fact counts, accepted rules. Models should call this first. |
| `egm_ask` | Facts matching a pattern, each labelled stated, current or inferred, with proofs. `include_history` adds past values. |
| `egm_values` | Just the names that fill the `?`. The cheapest call. |
| `egm_ask_many` | Up to 50 patterns in one call, for multi-step questions. |
| `egm_history` | Past values, with when and per which source. |
| `egm_conflicts` | Stated facts the rules contradict, and disagreeing sources. |
| `egm_infer` | Facts derived by the rules, optionally for one relation. |

With `--writable`:

| Tool | Use |
|---|---|
| `egm_observe` | Record what a source says now (`snapshot`) or add to it (`partial`). Old values become history. |
| `egm_ingest` | Add plain facts. |
| `egm_save` | Persist additions to the save path (`--save-to`, default: the KB itself). |

Additions live in memory until `egm_save`. On exit, unsaved additions are discarded with a
warning on stderr, unless you pass `--autosave`.

**Strict by default.** `egm_ask`, `egm_values` and `egm_ask_many` default to `strict: true`, which
returns stated facts and law-tier inferences only. This is the policy that scored perfectly in the
tokenomics study. When strict mode hides something, the result says how many answers it hid, so
the model can retry with `strict: false`.

**Unknown relations.** If a pattern uses a relation the knowledge base hasn't learned, the result
says so and lists the relations it has, instead of returning an empty list. Models can recover in
one step rather than concluding "no answer".

**Empty means unknown.** An empty `egm_ask` or `egm_values` result carries the note "no stated or inferred answer:
unknown, not false". If the knowledge base hit a cap (for example `MAXWORDS` smaller than the vocabulary), the note
names the cap and says the name may lie beyond it. In a recorded session an agent read an empty answer under the cap
as "not in the knowledge base" (`docs/AGENT_SESSIONS.md`, session 0). Serve with a sized `MAXWORDS` to avoid it.

Every result is JSON, sent both as text and as `structuredContent`. Logs go to stderr.

## Protocol

Supported: 2025-11-25, 2025-06-18, 2025-03-26 and 2024-11-05, through the `initialize` handshake.
Methods: `initialize`, `ping`, `tools/list`, `tools/call`, plus empty `resources/list` and
`prompts/list`.

**Not yet supported:** the stateless 2026-07-28 revision (no handshake, `server/discover`,
`resultType` on every result). Stdio clients that speak it fall back to the handshake, so they
still connect.

`make test` runs the protocol tests. `make interop` also drives the server with the official MCP
Python client.
