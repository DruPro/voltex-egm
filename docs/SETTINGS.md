# Engine settings

Generated from the engine's settings registry (`CONFIG` command). Every setting is saved with a
knowledge base in `<file>.cfg` except diagnostics, and `SET` after `LOAD` overrides a saved value.

**Experimental** settings are study options: off by default, tested, but not recommended for all
data. Turning one on makes `RELATIONS` print `[CONFIG] experimental settings on: ...`.

| Setting | Default | Layer | Status | What it does |
|---|---|---|---|---|
| `CLASS` | 0.5 | statistics | stable | similarity needed to merge words into a category |
| `RATE` | 0.4 | induction | stable | minimum share of chains whose conclusion is stated |
| `LIFT` | 5 | induction | stable | minimum rate over the conclusion's base rate |
| `SUPPORT` | 3 | induction | stable | minimum confirming chains for a rule |
| `PCA` | 0.8 | induction | stable | minimum agreement where the answer is known |
| `LAW` | 0.95 | induction | stable | reliability needed for the law tier |
| `COVERAGE` | 1 | induction | stable | relax the rate bar when data looks sparse (1/0) |
| `LABELS` | 1 | induction | stable | label rules and facts law or tendency (1/0) |
| `CHAIN` | 2 | induction | **experimental** | longest rule body, 2-8 premises (studies/multipremise) |
| `CONDITIONS` | 0 | induction | **experimental** | learn group conditions on accepted rules (1/0) (studies/multipremise) |
| `DEPTH` | 4 | inference | stable | inference rounds, 0 = until nothing new (studies/depth) |
| `CORROBORATE` | 1 | inference | stable | a contradiction needs two distinct rules (1/0) |
| `OBS` | 1 | evidence | stable | project the observation log (1/0) |
| `STALE` | 1 | evidence | stable | staleness checks after updates (1/0) |
| `CHGREMOVALS` | 1 | evidence | stable | only removals feed the change signal (1/0) |
| `SAMEFIX` | 1 | evidence | stable | same-rule re-derivation confirms a stale candidate (1/0) |
| `DX` | 0 | evidence | **experimental** | explained staleness for observations (1/0) |
| `DECL` | 0 | evidence | **experimental** | declarative amendment records (1/0) (earlier study) |
| `DECLMINE` | 0 | evidence | **experimental** | mine amendment records as facts (1/0) (earlier study) |
| `DECLFN` | 0 | evidence | **experimental** | one-value fix for amendments (1/0) (earlier study) |
| `REFRESH` | 0 | build | **experimental** | reuse classes and rules for small changes (share of records, 0 = off) |
| `PROFILE` | 0 | diagnostics | stable | print timings (1/0) |

## The experimental options, and the evidence

- `CHAIN` (2-8): rules with more than two premises. Excellent on chain-shaped data (family trees:
  3,000 correct inferences, 0 wrong, where the default makes none). Lowers precision on
  coincidence-rich data (hidden world: 0.955 to 0.931 at 3, 0.903 at 4) and is slower. See
  `studies/multipremise/RESULTS.md`.
- `CONDITIONS` (0/1): restricts a rule to the group it actually holds for. Found the hidden
  world's true rule (only farmers and miners harvest), cut those errors 98%, best precision of
  any configuration (0.980). One spurious condition from 9 cases remains. Same study.
- `DX`, `DECL`, `DECLMINE`, `DECLFN`, `REFRESH`: options from earlier studies of change
  handling and rebuild speed; see `docs/papers/`.

`DEPTH` is stable: `SET DEPTH 0` runs inference until nothing new is derived (`studies/depth/`).
