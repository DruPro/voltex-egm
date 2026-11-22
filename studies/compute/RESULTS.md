# Can tree inference compute? Results

Pre-registered: `PREREGISTRATION.md` (hash in `prereg_hash.txt`). One exploratory configuration was added afterwards
(`DEVIATIONS.md` 1). Every number here comes from `results/` (`tools/run.py`; verdicts:
`tools/run.py verdicts`). No engine change.

## Verdicts

| Prediction | Verdict |
|---|---|
| C1 functional completeness: NAND-only circuits | **pass** |
| C2 mixed gates, 8-bit adders, a one-input gate | **fail** (seed 1) |
| C3 a 3-input rule (Rule 110 gate) | **pass** |
| C4 unrolled Rule 110 automaton, 16 × 16 | **pass** |
| C5 `DEPTH 4` recovers no more than `DEPTH 0`, with 0 wrong | **fail** (seed 1's 47 wrong) |
| C6 controls: nothing without `TREES`; no law-tier answer for a random gate | **pass** |
| C7 every run under 120 s | **pass** (the slowest took 0.41 s) |

## All runs (3 seeds summed; circuits fully correct)

| World | Configuration | Wires correct | Wrong | Unanswered | Circuits fully correct | Max s |
|---|---|---|---|---|---|---|
| `nand` | `trees_depth0` | 3,330 / 3,330 | 0 | 0 | add4 60/60, fulladd 90/90, xor 90/90 | 0.17 |
| `nand` | `trees_depth4` | 2,597 / 3,330 | 0 | 733 | add4 0/60, fulladd 9/90, xor 90/90 | 0.1 |
| `nand` | `notrees` | 0 / 3,330 | 0 | 3330 | add4 0/60, fulladd 0/90, xor 0/90 | 0.05 |
| `nand` | `trees_depth0_lawonly` | 3,330 / 3,330 | 0 | 0 | add4 60/60, fulladd 90/90, xor 90/90 | 0.17 |
| `mixed` | `trees_depth0` | 1,332 / 1,440 | 47 | 61 | add8 20/30, mux 49/60 | 0.41 |
| `mixed` | `trees_depth4` | 1,192 / 1,440 | 47 | 201 | add8 0/30, mux 49/60 | 0.2 |
| `mixed` | `notrees` | 0 / 1,440 | 0 | 1440 | add8 0/30, mux 0/60 | 0.05 |
| `mixed` | `trees_depth0_lawonly` | 1,440 / 1,440 | 0 | 0 | add8 30/30, mux 60/60 | 0.4 |
| `rule110` | `trees_depth0` | 900 / 900 | 0 | 0 | automaton 3/3 | 0.13 |
| `rule110` | `trees_depth4` | 372 / 900 | 0 | 528 | automaton 0/3 | 0.06 |
| `rule110` | `notrees` | 0 / 900 | 0 | 900 | automaton 0/3 | 0.03 |
| `rule110` | `trees_depth0_lawonly` | 900 / 900 | 0 | 0 | automaton 3/3 | 0.13 |
| `rnd` | `trees_depth0` | 33 / 180 | 31 | 116 | - | 0.1 |
| `rnd` | `trees_depth4` | 33 / 180 | 31 | 116 | - | 0.1 |
| `rnd` | `notrees` | 0 / 180 | 0 | 180 | - | 0.04 |
| `rnd` | `trees_depth0_lawonly` | 0 / 180 | 0 | 180 | - | 0.09 |

`trees_depth0_lawonly` is exploratory.

## What it shows

- **It computed with gates it learned itself.** The engine was never given a truth table. From example gates
  alone it learned each gate's behaviour as tree rules, then chained them through circuits it had never seen.
  - **NAND alone:** XOR, full adders and 4-bit adders built from NAND gates are all correct (3,330 of 3,330 wires
    over 3 seeds). NAND is functionally complete, so any boolean function can be written this way.
  - **8-bit adders:** the carry chain is 17 gates deep, and these were all correct in seeds 0 and 2.
- **It learned minimised logic, not the table.** For Rule 110 it accepted six rules that together cover all eight
  rows exactly, each at agreement 1.00. Some rows merge: for example, "centre zero and right zero ⇒ zero" covers
  both `100` and `000`.

  | Learned rule (Rule 110 gate `g`, output `a`) | Agreement | Known cases |
  |---|---|---|
| `has third input(g,y1) & has value(y1,one) & has second input(g,y2) & has value(y2,one) & has first input(g,y3) & has value(y3,one) => has value(a,zero)` | 1.00 | 35 |
| `has third input(g,y1) & has value(y1,one) & has second input(g,y2) & has value(y2,zero) => has value(a,one)` | 1.00 | 48 |
| `has third input(g,y1) & has value(y1,zero) & has second input(g,y2) & has value(y2,zero) => has value(a,zero)` | 1.00 | 47 |
| `has third input(g,y1) & has value(y1,zero) & has second input(g,y2) & has value(y2,one) => has value(a,one)` | 1.00 | 51 |
| `has second input(g,y1) & has value(y1,one) & has first input(g,y2) & has value(y2,zero) => has value(a,one)` | 1.00 | 45 |
| `has third input(g,y1) & has value(y1,one) & has first input(g,y2) & has value(y2,zero) => has value(a,one)` | 1.00 | 41 |

- **It ran a bounded slice of a universal computation.** Given only the first row, it computed a 16-cell,
  16-step Rule 110 automaton (240 cells) with 0 errors in each seed. Rule 110 is Turing complete in the limit; this
  is a bounded run of it.
- **Depth is the bound on computation.** At the default `DEPTH 4`, the automaton stops at gate depth
  4: 124 of 300 cells, every one correct and the rest unanswered. It answers what it
  can compute and leaves the rest blank. `DEPTH 0` runs to the fixpoint.
- **It doesn't make up a rule for the random gate.** With no rule to learn, no answer about the random gate was law
  tier. By default, 18-27 of 60 got a tendency-tier guess per seed, and 33 of 64 guesses were right: chance accuracy, labelled as a guess. With law-only proofs it answered none.

## Where it went wrong

- **Mixed gates, seed 1:**

  | Seed | Correct | Wrong | Tiers |
  |---|---|---|---|
| 0 | 480 / 480 | 0 | {'law correct': 480} |
| 1 | 372 / 480 | 47 | {'tendency correct': 143, 'law correct': 229, 'tendency wrong': 47} |
| 2 | 480 / 480 | 0 | {'law correct': 480} |

  - **What it learned:** the same exact gate rules as the other seeds, plus one tendency rule, "an AND gate's
    output is zero". That is AND's base rate, at agreement 0.80, ignoring the inputs.
  - **What it cost:** where that rule disagreed with the exact rule, wrong values and abstentions spread down the
    carry chains. Every wrong answer is labelled tendency.
  - **The general pattern:** the same as in the code studies, a general shortcut competing with exact rules.
  - **Exploratory:** with law-only proofs (`TENDENCYSTEPS 0`), seed 1 is 480 of 480. Every computable world is
    then correct in every seed, and the random gate gets no answer at all.

## Turing completeness: the answer

No, and this study wasn't expected to show it. Inference creates no new entities, never overwrites a value, and
always stops, so it can't extend its memory or loop without bound. What it does, measured here:
- it learns step functions (gates, a cellular-automaton rule) from examples;
- it evaluates any circuit or unrolled computation laid out in the data, as deep as `DEPTH` allows (all the way
  with `DEPTH 0`);
- it computes correctly at law tier, and leaves blank what it can't compute.

In complexity terms: the data supplies a bounded circuit, and the engine learns its gates and runs it. The bounds
on computation are the size of the grid in the data and the depth setting.
