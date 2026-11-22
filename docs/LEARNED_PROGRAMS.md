# Learned rules as programs: a research report

This report summarises one line of work: can rules that Voltex EGM learns from examples act as programs, and what
does it take to run them? It is a synthesis. Every number comes from a study's results files. The studies were
pre-registered; failures are reported next to the passes.

| Study | Question | Where |
|---|---|---|
| Computation | Can tree inference compute? | `studies/compute` |
| Harness | Learn once, compute later; can a loop supply memory and a clock? | `studies/harness` |
| Inferred programs | Can learned rules themselves be executed, without learning from runtime state? | `studies/inferred_program` |
| REFRESH for trees | The engine change that keeps learned tree rules across state changes | `studies/refresh_trees` |
| Mimic | A language built on all of the above | `lang/mimic` (`REPORT.md`, `bench/`) |

## 1. Inference computes, within bounds

The engine was never given a truth table. It learned each gate from example gates, as tree rules, then evaluated
circuits it had never seen (`studies/compute`, 3 seeds):
- **NAND-only circuits:** 3,330 of 3,330 wires right. NAND is functionally complete, so any boolean function can be
  built from it.
- **Rule 110:** learned as a minimised cover of six rules, each at agreement 1.00. A 16-cell, 16-step automaton was
  computed from its first row, 720 of 720 cells right.
- **Mixed gates and 8-bit adders:** perfect in two seeds. In the third, a base-rate shortcut ("an AND gate outputs
  zero", agreement 0.80) caused 47 wrong values, all labelled tendency. With law-tier proofs only, every computable
  world was correct in every seed.

**Not Turing complete on its own.** Inference creates no entities, never overwrites a value, and always stops. It
evaluates any bounded computation laid out in the data, as deep as `DEPTH` allows.

## 2. A harness supplies memory and a clock

`studies/harness`, round 2:
- **Learn once, compute later.** Gates taught once; 30 new 8-bit adders computed from their wiring alone, 270 of 270
  outputs.
- **A learned Turing machine.** The transition table was learned from isolated example steps; no run was ever shown.
  A harness holding the tape and the clock ran the 3-state busy beaver (14 of 14 steps, the simulator's tape) and
  binary increment on 48 inputs, including all-ones inputs whose tape grows.
- **No guessing.** A transition left untaught stopped every run that needed it, with "unknown".
- **Data needed.** Gates: nothing was computed below 32 examples per kind, part at 64-100, everything at 200.
  Transitions: 64 examples per row. The majority value ("write 1")
  takes the most data, because evidence is measured against the base rate.
- **Round 1 failed** because all outputs shared one relation with 10 values, and the tree search ignores targets
  with more than 8. That limit is now documented.

## 3. The learned rules are the program

The owner's hypothesis (`studies/inferred_program`): *Voltex can learn a program from examples, then execute it by
repeatedly applying its learned rules to changing state, without treating runtime state as new learning evidence.*

**The engine already has the two phases.** Rule mining reads stated facts only. Inference applies a fixed rule list,
round after round, over stated and derived facts, so a derived value feeds the next round without becoming
evidence.

| Program | One inference pass | Derived facts stated | Output rules with vs without runtime state |
|---|---|---|---|
| State machine (mod-3 counter), 20 × 64 steps | 1,280 / 1,280 | 0 | identical |
| Recursion (ancestry) | 858 / 858 | 0 | identical |
| 8-bit adders | 90 / 90 | 0 | identical |
| Rule 110, 32 × 15 steps | 480 / 480 | 0 | identical |

- **Provenance is complete.** Every checked answer's proof reaches stated facts. Every rule used was traced to its
  supporting examples, and the counts recovered outside the engine equal the engine's own, for 22 of 22 rules.
- **Failure is honest.** An untaught symbol, an untaught state, or a contradictory transition stopped execution at
  exactly the first undecidable step, with no wrong law-tier answer.
- **The gap.** Across passes (state changing between inference runs), composition programs already kept their rules
  with `REFRESH` (0.9 ms per step), but tree programs relearned at every step (19 ms). The cause was located in
  `remapRules`.

## 4. The engine change: REFRESH keeps tree rules

Approved by the owner and tested in `studies/refresh_trees`:
- **The change:** `REFRESH` now re-attaches every relation a rule references (premises, conclusion, path steps, the
  condition relation with its subjects recomputed, tree branches), and is allowed with `TREES`. It is off by
  default.
- **Equivalence when off:** byte-identical on the gate (221 of 221) and the stress bench (294 of 295; the remaining
  cell hits the memory cap on both).
- **Tree programs across passes** (state machine, busy beaver, increment): 109 of 109 steps right, every one
  identical to an engine relearning every step, with 0 relearns after the first build.
- **Cost:** 2.5-2.7× lower per step. The prediction was 3×, so it fails as written: each step still re-projects
  relations and reruns full inference.

**Not a mark of non-evidence.** `REFRESH` defers learning, and a full build learns from every stated fact present.
The owner decided against a separate working-memory fact type for now; turning `REFRESH` on gives the practical
benefit.

## 5. Mimic: a language on top

`lang/mimic`: functions, Turing machines, circuits and cellular automata, all taught by rows of examples. Bench, 8
programs × modes, against a literal interpreter:
- **Learning:** 14 of 14 definitions learned to 100% of their taught rows.
- **Correctness:** 0 wrong results in any mode.
- **Speed:** `refresh` mode keeps the learned rules while programs run. The busy beaver went from 39 to 12 ms per
  step, with a flat per-step cost (exploratory).
- **Recursion:** recursive top-down questioning matched chained inference at 13× the questions. It's redundant for
  computing and kept as `why`, for reading proofs.

## 6. Engine behaviours found along the way (reported, not changed)

| Behaviour | Effect | Evidence |
|---|---|---|
| Tree targets limited to 8 distinct values | larger value sets are silently not learned | `studies/harness` deviation 1 |
| OBSERVE snapshot loss | a record's current snapshot vanishes after 13-26 restatements when plain facts also name its entity | `lang/mimic/repro_observe_loss.py` |
| Facts dropped through categories | a word that falls out of its slot's category takes its facts out of the relation, with no warning (Mimic lost 64 facts when a second program shared values) | `lang/mimic/REPORT.md` §5.3 |
| Remove-only changes | the refresh size counter is unsigned, so a change that only retracts always relearns | `studies/refresh_trees` deviation 1 |
| Exact exceptions outvoted | general rules outvote an exact specific rule on single-valued relations | `studies/strengths`, `studies/compute` |

## 7. Open questions

- **Incremental inference:** touching only what a state change affects, without slowing the program or changing its
  results. The next cost step.
- **Scale:** these were knowledge bases of a few thousand to 20,000 taught facts.
- **Generalisation:** the engine abstains on cases the examples don't determine. Whether richer example sets teach
  real generalisation is untested.
- **Programs that need fresh entities every step** (an unbounded tape) still relearn, unless the cells are recycled.
