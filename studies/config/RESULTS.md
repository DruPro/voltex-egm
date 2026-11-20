# Configuration persistence: results

Pre-registration: PREREGISTRATION.md (sha256 56d089ab…, 2026-11-20T17:52:32Z). No deviations.

| Prediction | Result | Verdict |
|---|---|---|
| C1 no settings changed: byte-identical to 2.2.1 (22 datasets, each saved and reloaded) | 22/22 identical | Pass |
| C2 bug case: `SET RATE 0.1`, save, fresh `LOAD` | 7,169 facts (2.2.1: 90); prints `[CONFIG] restored from kb.vtx.cfg: RATE=0.1` | Pass |
| C3 knowledge base without `.cfg` behaves as 2.2.1 | 90 at defaults; 7,169 with `SET RATE 0.1` before `LOAD`, same as 2.2.1 | Pass |
| C4 `SET` after `LOAD` overrides; SDK settings override the saved profile | 90 after `SET RATE 0.4`; SDK test passes | Pass |
| C5 all existing tests plus new persistence tests | 30/30 kit checks; 40 SDK and MCP tests (3 new) | Pass |
| C6 sanitizers | full suite and 7 save/load/config runs, 0 errors | Pass |

What changed: a registry of 22 settings (name, owning layer, default, experimental flag,
saved flag, description) now drives `SET`, the new `CONFIG` command, and save/load. `SAVE`
writes `kb.vtx.cfg` next to the knowledge base; keep the two files together, as with `.obs`.
`RELATIONS` announces experimental settings when any is on. The Python SDK gained
`Engine.config()` and now applies its `settings` argument after loading.
