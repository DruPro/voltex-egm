# Configuration persistence and a settings registry

Motivation: studies/multipremise/CONFIGURATION.md, Finding 1 (settings are not saved, so the
same knowledge base gave 7,169 or 90 inferred facts) and Finding 2 (no single declaration of
the settings).

## Design (decided before implementation)

- **Registry.** One table declares every setting: name, owning layer, default, whether it is
  experimental, whether it is saved, and a one-line description. `SET`, the new `CONFIG`
  command, and save/load all use it. `PROFILE` (diagnostics only) is not saved.
- **Saving.** `SAVE path` also writes `path.cfg`: a version line plus one `KEY value` line per
  saved setting that differs from its default. The `VTX2` file is unchanged.
- **Loading.** If `path.cfg` exists, `LOAD` resets every saved setting to its default, applies
  the file, and prints `[CONFIG] restored from path.cfg: KEY=value ...` when any value is not
  the default. If it does not exist (a knowledge base saved by 2.2.1 or earlier), settings are
  left exactly as they were: today's behavior.
- **Overrides.** Anything `SET` after `LOAD` wins. The Python SDK applies the `settings` given
  to `Engine(...)` / `egm.open(...)` after loading, so explicit settings override saved ones.
- **Visibility.** `CONFIG` prints every setting with its value, default, layer and status.
  When an experimental setting (`CHAIN`, `CONDITIONS`) is not at its default, `RELATIONS`
  prints `[CONFIG] experimental settings on: ...` before its usual output.

## Predictions

- **C1.** With no settings changed, byte-identical to frozen 2.2.1 on the 22-dataset gate
  (which saves and reloads every dataset).
- **C2.** The bug case is fixed: `SET RATE 0.1`, ingest, `SAVE`; a fresh engine that only runs
  `LOAD` and `INFER ALL` derives 7,169 facts (2.2.1: 90).
- **C3.** A knowledge base without a `.cfg` behaves exactly as with 2.2.1, including a `SET`
  made before `LOAD`.
- **C4.** `SET` after `LOAD` overrides the saved value (back to 90 with `SET RATE 0.4`), and the
  SDK's `settings` argument overrides the saved profile.
- **C5.** All existing kit, SDK and MCP tests pass, plus new persistence tests.
- **C6.** Sanitizer build clean on the gate datasets.
