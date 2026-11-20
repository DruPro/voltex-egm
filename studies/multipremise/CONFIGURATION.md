# Where should engine configuration live?

An investigation for the multi-premise study. Findings are from reading `src/voltex2.cpp`
(2.2.1) and one test; the recommendation is a design proposal, not yet implemented.

## Finding 1: settings are lost on save, so a saved knowledge base can change its answers

`SAVE` writes the vocabulary, grammar and record counts, and no settings. `LOAD` restores
defaults. Test (containment world):

```
SET RATE 0.1 → INGESTFILE → INFER ALL → SAVE    [INFER] 7169 new facts derived from 5 accepted rules
LOAD → INFER ALL                                 [INFER] 90 new facts derived from 3 accepted rules
```

The same file gives different answers depending on what the user remembers to re-set. `egm
build --set RATE=0.1` therefore saves a knowledge base that no longer behaves as it was
built, and `egm ask` / `egm mcp` on it silently use defaults. This is a reproducibility bug,
independent of the multi-premise work.

## Finding 2: there is no single place that knows what the settings are

Settings are fields scattered across the engine's main struct, set by one long `if/else`
chain in the `SET` command. The usage message lists 11 of the 19 keys. Many behavior-shaping
numbers are hard-coded.

| Owning layer | Settable today (`SET`) | Hard-coded today |
|---|---|---|
| 2 Statistics | `CLASS` (0.5) | 12,000 words considered; 4 merge rounds; category size ≥ 2 to be "open" |
| 3 Induction | `RATE` (0.4), `LIFT` (5), `SUPPORT` (3), `PCA` (0.8), `LAW` (0.95), `COVERAGE`, `LABELS`; study: `CHAIN`, `CONDITIONS` | z ≥ 3; known-answer cases ≥ 5; coverage relax factor 0.8; coverage needs inverse lift ≥ 20, k ≥ 10; 2–8 open slots; template support ≥ 3; at most 40 relations; one-value relation at 95% |
| 4 Inference | `CORROBORATE`; study: `DEPTH` | depth 4 (before the study); corroboration needs 2 distinct rules |
| 5 Evidence | `OBS`, `DX`, `STALE`, `CHGREMOVALS`, `SAMEFIX`, `DECL`, `DECLMINE`, `DECLFN` | UPDATE treats a relation as one-value at 90% |
| Build / diagnostics | `REFRESH`, `PROFILE` | study: path-search caps (50,000 steps, 200 candidates, 10,000 paths) |

## Recommendation: configuration is a declared profile, owned by no single layer

Configuration is not a stage of the pipeline, so it should not be a layer between two
others. It is a **cross-cutting declaration**: one engine profile that every layer reads
and none owns. Concretely:

1. **One registry.** Each setting is declared once with its name, owning layer, type,
   allowed range, default, whether it changes answers, and the version that introduced it.
   `SET`, the usage message, validation and documentation are all generated from that
   registry, so they can no longer drift apart (Finding 2).
2. **The profile travels with the knowledge base.** `SAVE` writes it (as a sidecar,
   `kb.vtx.cfg`, like the existing `.obs`, so the `VTX2` format and the equivalence gate stay
   untouched); `LOAD` restores it. Overriding a setting after loading is allowed but
   reported. An old file without a profile loads with defaults, which is today's behavior.
   This fixes Finding 1.
3. **Every answer can say what produced it.** A `CONFIG` command prints the effective
   profile, and `RELATIONS` prints any non-default settings in its header, so pasted output
   is self-describing and reproducible.
4. **Named presets.** `shipped` (exactly 2.2.1), `strict` (stated facts and laws only),
   `deep` (`DEPTH 0`), and `experimental` (study switches). The SDK, CLI and MCP server accept
   a preset or individual settings, and the MCP server reports which it uses.
5. **The gate rule becomes a property of the registry.** Every setting must declare a
   default that reproduces the previous version; `make test` runs the gate for the default
   profile and the repro tests for each preset.
6. **Expose what has been studied, keep the rest internal.** Promote a hard-coded number to a
   setting only once an experiment has measured its effect (for example depth, now). Keep
   performance caps internal but report them when they bind (for example, "path search
   capped for 12 entities"), because a silent cap is a hidden change in behavior.

Suggested order: the sidecar profile and `CONFIG` command first (they fix a real bug and
change no answers), then the registry, then presets.
