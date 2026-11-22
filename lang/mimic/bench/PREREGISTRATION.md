# Mimic bench: what a language built on learned rules can and can't do

Status: pre-registered before the bench runs. Hash in `prereg_hash.txt`. Method: `docs/EVALUATION.md`.

## What was seen before this file (exploratory, disclosed)

- **Phrasing:** relation phrases that differ in one word and share a tail ("reads inc symbol 1", "has inc symbol 1")
  made the engine read the verb as the open slot. Fixed in Mimic with single-token verbs (`inc_reads`,
  `inc_writes`).
- **Snapshot loss:** in `observe` mode, a record's current snapshot facts disappear after 13 snapshots (one fact
  each) or 26 (two). The same happens on a plain engine (`repro_observe_loss.py`). That is an engine behaviour,
  reported to the owner and not changed. `fresh` and `rebuild` were correct on the same run.
- **Constant outputs:** an output that is the same in every taught row can't be learned (it never varies, so no
  rule beats the base rate). Mimic applies it as declared, and labels it.

## Programs (fixed)

The 8 programs in `examples/`: `hello`, `adder`, `add8`, `increment`, `busy_beaver`, `parity`, `rule110`,
`guess`.

## Reference

`bench.py` contains a literal interpreter. It executes each program's tables directly, including the `?` rows,
which are the author's intended meaning. It never uses the engine.

## Measurements

- **B1.** Every `eval`, `run` and `automaton` result in each mode (`observe`, `fresh`, `rebuild`), compared with
  the reference: right, wrong, or unknown (Mimic stopped or reported UNKNOWN).
- **B2.** Cost by mode: learning time; ms per machine step, as a function of run length (increment on 4, 8, 16,
  32 and 64 ones).
- **B3.** Untaught rows (`guess`): what the engine inferred for each. Descriptive.
- **B4, recursive questions.** On `add8`, compare three ways of evaluating:
  - `DEPTH 0` bottom-up;
  - `DEPTH 1` bottom-up;
  - `DEPTH 1` with top-down recursive questions, where the harness asks which gate produces a wire, evaluates its
    inputs, states them, and asks again.

  Measure results, number of engine questions, and time.
- **B5.** Determinism: every program run twice in `fresh` mode gives identical output.

## Predictions

- **P1.** `fresh` and `rebuild`: 0 wrong results. Every result that doesn't depend on an untaught row is right.
- **P2.** `observe`: 0 wrong results, and at least one unknown on `increment`'s 16-one run (the snapshot loss).
- **P3.** No mode gives a wrong result anywhere. Where Mimic can't decide, it says unknown.
- **P4.** Recursive questions at `DEPTH 1` give the same `add8` results as `DEPTH 0`. Plain `DEPTH 1` bottom-up
  leaves some outputs unknown.
- **P5.** Determinism holds for all 8 programs.

B2 and B3 are descriptive, with no thresholds.
