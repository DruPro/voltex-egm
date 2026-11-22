# Mimic bench: results

Pre-registered (`PREREGISTRATION.md`, hash in `prereg_hash.txt`). Written by `report.py` from `results.json` and
`verdicts.json` (`bench.py`). The reference is a literal interpreter of each program's tables that never uses the
engine.

## Verdicts

| Prediction | Verdict |
|---|---|
| P1 `fresh` and `rebuild`: 0 wrong; everything not depending on an untaught row right | **pass** |
| P2 `observe`: 0 wrong, and at least one unknown on the 16-one increment (snapshot loss) | **pass** |
| P3 no mode gives a wrong result anywhere | **pass** |
| P4 recursive questions at `DEPTH 1` give the `DEPTH 0` results; plain `DEPTH 1` leaves outputs unknown | **pass** |
| P5 every program deterministic | **pass** |

## B1: every result, every mode (right / total)

| Program | fresh | rebuild | observe |
|---|---|---|---|
| `hello` | 4/4 | 4/4 | 4/4 |
| `adder` | 8/8 | 8/8 | 8/8 |
| `add8` | 4/4 | 4/4 | 4/4 |
| `increment` | 4/4 | 4/4 | 3/4, 1 unknown |
| `busy_beaver` | 1/1 | 1/1 | 1/1 |
| `parity` | 3/3 | 3/3 | 3/3 |
| `rule110` | 1/1 | 1/1 | 1/1 |
| `guess` | 1/3, 2 unknown | 1/3, 2 unknown | 1/3, 2 unknown |

- **Totals:** `fresh` 26/28, `rebuild` 26/28, `observe`
  25/28.
- **Wrong anywhere:** 0.
- **Unknowns in `guess`:** these are the untaught rows, by design. Where the engine couldn't decide, Mimic stopped and
  said so.

## B2: cost per machine step (ms), by run length

Increment on n ones.

| n ones | fresh | rebuild | observe |
|---|---|---|---|
| 4 | 11.8 (halted, 5 steps) | 23.7 (halted, 5 steps) | 12.8 (halted, 5 steps) |
| 8 | 11.3 (halted, 9 steps) | 21.9 (halted, 9 steps) | 10.8 (halted, 9 steps) |
| 16 | 11.5 (halted, 17 steps) | 22.9 (halted, 17 steps) | 11.2 (halted, 17 steps) |
| 32 | 11.8 (halted, 33 steps) | 21.8 (halted, 33 steps) | 11.5 (unknown, 22 steps) |
| 64 | 13.5 (halted, 65 steps) | 21.8 (halted, 65 steps) | 11.2 (unknown, 22 steps) |

- **fresh:** 11.3-13.5 ms per step, flat up to 64 steps.
- **rebuild:** 21.8-23.7 ms per step. Every step relearns from the taught examples, so it costs about 2×
  `fresh` here. Its cost grows with what is taught, not with run length.
- **observe:** the same speed as `fresh`, but it stops with unknown once the record has been restated about 22
  times. That is the engine's snapshot loss (`repro_observe_loss.py`), and it is why `fresh` is the default.

**On re-ingesting.** You asked whether rebuilding from scratch might be more accurate and cheaper than OBSERVE.
- **Accurate:** yes. `rebuild` was right everywhere `observe` lost state.
- **Cheaper:** not here. `fresh`, which only adds the new step's facts to the running engine, is as accurate and
  about half the cost.

## B3: rows the engine was never shown (`guess`)

| Row | You meant | Engine inferred |
|---|---|---|
| `majority` 0 1 0 | 0 | unknown |
| `majority` 1 0 0 | 0 | unknown |
| `majority` 1 1 0 | 1 | unknown |
| `inc` carry _ | 1 left halt | ? left ? |

The engine didn't generalise to the untaught majority rows. The taught rows don't force a unique answer for them,
and no rule was supported strongly enough. For the untaught increment transition, it gave only the declared move.
In both cases it abstained instead of guessing.

## B4: recursive questions vs chained inference (`add8`, 4 evaluations)

| Method | Result | Engine questions per evaluation | Time per evaluation |
|---|---|---|---|
| depth0 bottom up | 4/4 right | 9 | 0.20 s |
| depth1 bottom up | 0/4 right, 4 unknown | 9 | 0.08 s |
| depth1 recursive | 4/4 right | 120 | 1.43 s |

**Is recursion redundant? For evaluation, yes.**
- **The comparison:** recursive questions (ask which gate makes a wire, evaluate its inputs, state them, ask again)
  reach the same answers as chained inference at `DEPTH 0`. They take about
  13×
  the questions and 7×
  the time.
- **Why:** the engine's own chaining already does the walk, in one fixpoint. Recursion only re-does it one level at
  a time.
- **The one result:** with inference capped at `DEPTH 1`, recursion recovers what the cap hides. It is a workaround
  for a depth limit, not a gain.
- **Untested here:** where it might still pay is selective evaluation on data whose full fixpoint floods (dpkg at
  `DEPTH 0`), because recursion computes only what is asked.
- **Where recursion is useful today:** reading proofs. `why` walks an answer's proof down to the given facts. That
  navigates a tree the engine already built, so it isn't redundant.

## What this measures about the engine

- **Learning operations from examples.** 14 functions and machines in 8 programs (1 to 3 inputs, up to 6
  transitions, 60 taught rows). 14 of 14 were learned to 100% of their taught rows, as checked on fresh
  probes (`learned` in `results.json`).
- **Composition.** Learned gates chained 17 deep (`add8`), a learned 3-input rule over 16 steps (`rule110`), and a
  busy beaver: all exact.
- **Reliability.** 0 wrong results in 3 modes over 8 programs. Every failure to decide is reported as unknown.
- **Boundaries met:**
  - at most 8 values per target relation;
  - constant outputs can't be learned;
  - majority values need about 64 examples;
  - relation phrases that differ in one word confuse the slots;
  - OBSERVE snapshots are lost after about 13-26 restatements.
