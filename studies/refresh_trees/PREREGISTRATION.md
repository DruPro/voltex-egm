# REFRESH for tree rules: keep learned rules across small state changes

Status: pre-registered before the engine change. Hash in `prereg_hash.txt`. Approved by the owner (2026-11-22):
"make REFRESH re-attach every relation a rule references, then allow it for tree rules too. Scope: general, off by
default, and byte-identical output when off." Why: `studies/inferred_program` (H3 and the decision rule). Method:
`docs/EVALUATION.md` §7.

## 1. Capability, and the owning layer

Inference as program execution across passes (capability matrix). The change sits in the build path
(`ensureModel`, `cacheRules` and `remapRules` in `src/voltex2.cpp`): induction is kept, relations are re-projected.

## 2. The change (two parts, nothing else)

1. **Re-attach every relation a rule references.** `cacheRules` stores the relation templates of every reference:
   `r1`, `r2`, `r3`, each `path` step, `condRel`, and each tree branch's `r` and `s`. `remapRules` maps all of them
   onto the rebuilt relations, and drops a rule if any of its relations is gone, as it already does for `r1`-`r3`.
   For condition rules, `condSubj` (subjects with a condition value, a snapshot taken at mining) is recomputed from
   the current facts.
2. **Lift the gate for `TREES`.** The refresh path is allowed when `TREES` is on. It stays off, as now, for
   `CHAIN 3+`, `CONDITIONS`, `REPLICATE` and `QUARANTINE`. Paths and conditions are re-attached correctly, but each
   needs its own validation before its gate is lifted.

`REFRESH` stays off by default (0). Constants in rules (`headVal`, branch constants, `condVals`) are word ids. They
stay valid because the refresh path already requires that no new words have appeared.

## 3. Baseline

`studies/refresh_trees/baseline_sha256.txt` records the current `src/voltex2.cpp` (commit `f4bd72d`), built
unchanged as the frozen baseline binary.

## 4. Predictions

- **R1, equivalence with `REFRESH` off.** The gate (`studies/scaling/tools/gate.py`, 221 cells) is byte-identical,
  new binary against baseline.
- **R2, equivalence on the existing refresh path.** The same dataset × settings cells run with `REFRESH 0.05`,
  through a script that changes evidence a little without new words: ingest every fact, `INFER ALL`, then retract
  and re-ingest 5 stated facts, `INFER ALL` again. Every cell whose settings don't include `TREES` is byte-identical
  between baseline and new. Cells with `TREES` are allowed to differ, since that is the new path.
- **R3, tree programs keep their rules.** P1 (the mod-3 state machine, `studies/inferred_program`) in the stepwise
  loop with `REFRESH 0.05`, and the busy beaver and binary increment (`studies/harness`), driven with one recycled
  step entity:
  - every step correct against the simulator;
  - exactly one full build per run;
  - a refresh build at every later step.
- **R4, the same answers as relearning.** At every step of R3, the refresh-path answer equals the answer of a second
  engine run in lockstep with `REFRESH 0` (full relearn) on the same facts.
- **R5, cost.** On P1's loop, time per step with the new path is at least 3× lower than with `REFRESH 0`.
- **R6, safety.** If a new word appears mid-run, that step takes a full build. A rule whose relation disappears is
  dropped (checked with a retracted relation).
- **R7, no regressions.** `make test` passes, and `make sanitize` is clean, including a sanitizer run of the R3 loop.

Any R1 difference, any R2 difference outside the `TREES` cells, or any R4 mismatch rejects the change.
