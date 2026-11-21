# Tree-shaped rules: results

Pre-registration: PREREGISTRATION.md (sha256 08b81ba2…, 2026-11-20T18:08:01Z). Deviation D1
(performance only, verified byte-identical) in DEVIATIONS.md. Gate: `TREES 0` byte-identical to
2.2.1 on 22/22 datasets; sanitizer clean with `TREES`, `CONDITIONS` and `DEPTH 0` on.

## Verdicts

| Prediction | Result | Verdict |
|---|---|---|
| T1 gates: `TREES 0` infers nothing; `TREES 1` ≥ 95% right, ≤ 1% wrong | 0 vs **1,319 / 1,332 right (99.0%), 0 wrong** | Pass |
| T2 decoy `rnd` gates: nothing inferred, no rule names `rnd` | 0 / 337 inferred; 0 rules | Pass |
| T3 adders, `DEPTH 0`: ≥ 95% fully correct, ≤ 1% wires wrong | **100 / 100 adders; 1,700 / 1,700 wires; 0 wrong** (8 rounds) | Pass |
| T3 exploratory, `DEPTH 4` | 36 / 100 adders; 1,568 / 1,700 wires; 0 wrong | — |
| T4 hidden world: precision −≤ 0.01 (mean), −≤ 0.03 (any run); recall not lower | 0.9545 → 0.9498 (−0.005); worst run −0.013; recall 0.4894 → 0.4960, higher in all 15 runs | Pass |
| T5 company world: precision not below `TREES 0` on any dataset | clean 100 → 100; noisy 99.9 → 100; noisy15 99.7 → 100; **noisy30 100 → 97.9%** | **Fail** |
| T6 unchanged worlds | divisibility, grandparent, containment unchanged; **remainders 192 → 222 / 225, 0 wrong** | **Fail** (changed, for the better) |
| T7 cost (exploratory) | rule mining: gates 0.13 s, adders 0.08 s, hidden world 56 s (original) / 9 s (after D1) | — |

## What was learned

**Tree rules learned logic gates from examples, in their simplest form.** For OR the engine
learned "either input is one ⇒ output is one" (one input suffices); for AND, "either input is
zero ⇒ zero"; XOR and NAND as the patterns that genuinely need both inputs. The
branch-economy rule (each branch must raise agreement by 0.10) is what keeps the rules
minimal. The decoy gates with random outputs produced no rule and no inference.

**The learned gates evaluated circuits they never saw.** Every one of 100 four-bit adders,
built from gates whose behavior was taught only on separate example gates, computed the
correct sum, with every internal wire correct. This needs inference to run until nothing new
is derived (8 rounds here); at the old 4-round limit only 36 adders finished, with none wrong.
This is a calculator whose logic was learned from examples, within the bound that the circuit
itself is given as facts.

**On real-world-like data, trees cost little and found both real rules and a designed decoy.**
In the hidden world they recovered the designed rule "your profession's institution is your
membership" and the designed decoy "your mentor's profession is yours" (true 90% of the time,
mostly labelled tendency). At least one five-step coincidence was accepted from 8 cases: when
a value is rare (base rate 1 in 8), a few matches clear even a corrected significance bar.
That is a known weakness of significance tests on tiny samples.

**The two failed predictions.**
- T5: on the company dataset with 30% wrong facts, trees derived 253 more facts, 231 correct
  and 22 wrong, so precision fell from 100% to 97.9%. Trees trade some precision for recall
  when the data itself is very noisy.
- T6: remainders improved from 192 to 222 of 225 with 0 wrong. Trees learned the remainder
  rule in reverse as well ("a number three above you has your remainder"), reaching numbers
  with no taught number below them. A failed prediction, reported as such, in the good direction.

**Cost.** The original candidate search took 56 s on the densest file because it rebuilt the
same features for every subject and target value. D1 cut this to about 9 s with identical
results. It remains the slowest setting on dense data.

## Recommendation

Keep `TREES` experimental, off by default. It is the only setting that reaches circuits and
multi-input logic, and it was harmless on the hidden world, but it costs precision on very
noisy data and admits rare-value coincidences from small samples. Next: a minimum sample size
for rare values (or a test that is exact for small counts), and a faster search on dense data.

## Reproducing

`hidden/gen_worlds.py` (generators), `tools/t1_t2_gates.py`, `tools/t3_adders.py`,
`tools/t4_hidden_world.py`; T5 and T6 reuse the company-world evaluator and the programming-by-
example scripts. Set `VOLTEX` to the engine binary.
