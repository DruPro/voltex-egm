# REFRESH for tree rules: results

Pre-registered: `PREREGISTRATION.md` (hash in `prereg_hash.txt`); baseline: `baseline_sha256.txt`; deviations:
`DEVIATIONS.md` (the R6(b) check fixed, and the stress bench added to R1). Numbers come from the results files in
this folder (`tools/report.py`).

**The change** (`src/voltex2.cpp`, 1 file changed, 31 insertions(+), 4 deletions(-)):
- `cacheRules` and `remapRules` now keep and re-attach every relation a rule references: premises, conclusion, path
  steps, the condition relation (with its subjects recomputed from the current facts) and tree branches.
- The refresh path is allowed with `TREES`.

`REFRESH` stays off by default.

## Verdicts

| Prediction | Verdict | Result |
|---|---|---|
| R1 `REFRESH` off: byte-identical to the baseline | **pass** | gate 221/221; stress bench: identical 294, different 0, not comparable 1, missing 0 |
| R2 existing refresh path unchanged | **pass** | 204/204 non-tree cells identical. The 17 tree cells: 17 identical to the baseline's full relearn, with the new path taken in 16 (baseline: 0) |
| R3 tree programs keep their rules, every step correct | **pass** | 109/109 steps correct; 0 full relearns after the first build; a refresh build at every later step |
| R4 the same answers as relearning every step | **pass** | 109/109 steps identical to a lockstep engine with `REFRESH 0` |
| R5 at least 3× cheaper per step | **fail** | 2.4-2.6×. Learning is gone; relation re-projection and full inference remain |
| R6 safety | **pass** | a new word forces a full build; a rule whose relation vanished is dropped on the refresh path, with the same answers as relearning |
| R7 no regressions | **pass** | `make test` 30/30 and 74 tests; `make sanitize` clean; the R3-R6 loops under the sanitizer binary give the same results |

## Tree programs across passes

One recycled step entity per program. Each step retracts the old state and ingests the new, and is asked
identically of two engines: the new path (`REFRESH 0.05`) and full relearning (`REFRESH 0`).

| Program | Correct | Same as relearning | Full relearns after the first | Refresh builds | ms/step, new | ms/step, relearn | Speedup |
|---|---|---|---|---|---|---|---|
| P1 state machine | 64/64 | 64/64 | 0 | 63 | 8.03 | 19.63 | 2.4× |
| bb3 | 14/14 | 14/14 | 0 | 13 | 31.17 | 79.64 | 2.6× |
| inc | 5/5 | 5/5 | 0 | 4 | 30.8 | 79.42 | 2.6× |
| inc | 9/9 | 9/9 | 0 | 8 | 31.45 | 79.41 | 2.5× |
| inc | 17/17 | 17/17 | 0 | 16 | 30.87 | 79.07 | 2.6× |

## What this changes

- **Every program shape tested now runs across passes without relearning:** the state machine, the busy beaver and
  binary increment, driven step by step from rules learned once. Earlier, `studies/inferred_program` H3 found tree
  programs relearning at every step.
- **R5 failed as written.** The remaining cost per step is re-projecting relations and running inference over the
  whole knowledge base, including the taught examples. A step can't yet touch only the facts it changed.
- **Not a mark of non-evidence.** `REFRESH` defers learning; it doesn't exempt runtime facts. A full build (a new
  word, a large change, a setting change) learns from every stated fact present, runtime state included. Because
  the harness retracts the previous state, at most the current state is present.

## Reported to the owner, not changed

The refresh condition computes the size of the change as `recordsIngested - recsAtFull` in unsigned arithmetic. A
change that only removes facts makes it negative, so it wraps, and the condition fails: a full build. That errs
toward relearning, so it's safe, but it means retractions alone never take the refresh path (`DEVIATIONS.md` 1).
