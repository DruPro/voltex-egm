# Demonstration: fixing self-sourced coverage (`COVSELF`, Round 3 prototype)

**The defect** (`studies/round2/CONFIRMATION.md`): a relation's coverage estimate comes from its best inverse rule,
on the assumption that the rule is a law. That same rule's reliability is then rate / coverage = rate / rate = 1.0,
whatever its agreement. On Round 2's `reversed_weak`, the decoy `requires(a,b) => suggests(b,a)` (agreement 0.14)
was admitted by strict this way.

This is a prototype on branch `round3-covself`, off by default (gate unchanged), measured on development data only.
Round 2's confirmation worlds are development data now. Script: `covself_demo.py`; full tables in `REPORT_*.md`.

## Two versions

- **`COVSELF 1` (naive):** the source rule is judged by a different estimate: the best other inverse rule for the
  relation, else the median of estimates that don't involve this relation, else none.
- **`COVSELF 2` (mirror test):** the source rule keeps its rating unless the evidence contradicts it from the other
  direction. If `A(a,b) => B(b,a)` were a law, the mirror `B(a,b) => A(b,a)` would be confirmed at A's coverage. If
  another rule about A is confirmed significantly more often than that allows, the inverse is not a law.

## Why the naive version fails

On its own numbers, a true inverse with 70% coverage is indistinguishable from a 70%-reliable tendency. `COVSELF 1`
rejects the decoy, and it also demotes true inverse and symmetric laws. Strict loses all recall on Round 1's
`inverse` and `symmetric` worlds (1.0 → 0) and recall on `company` (0.50 → 0.28).

| rule | world | agreement | `COVSELF 0` | `COVSELF 1` | `COVSELF 2` |
|---|---|---|---|---|---|
| `serves ⇒ is served by` | inverse | 1.00 | admitted | admitted | admitted |
| `is served by ⇒ serves` (true, 70% stated) | inverse | 0.70 | admitted | **rejected** | admitted |
| `is paired with` (true, symmetric) | symmetric | 0.83 | admitted | **rejected** | admitted |
| `requires ⇒ suggests` (decoy) | reversed_weak | 0.14 | **admitted** | rejected | rejected |

## What `COVSELF 2` changes (means over 5 seeds or splits)

**With `COVSOURCE 1`** (Round 2's coverage fix), the decoy world is fixed, and only strict on the `hidden` worlds
changes elsewhere:

| world | profile | precision | recall | wrong answers |
|---|---|---|---|---|
| reversed_weak | default, tendency | 0.138 → **1.000** | 1.000 → 1.000 | 1,128 → **0** |
| reversed_weak | strict | 0.000 → abstains | 0 → 0 | 948 → **0** |
| hidden-cov30 | strict | 0.997 → 0.996 | 0.351 → 0.339 | 8 → 8 |
| hidden-cov50 | strict | 0.998 → 0.998 | 0.463 → 0.462 | 6 → 6 |
| every other development, sealed and real world | all | unchanged | unchanged | unchanged |

**With the current default (`COVSOURCE 0`)**, it also helps the flooding worlds, but it costs strict real recall on
code:

| world | profile | precision | recall | wrong answers |
|---|---|---|---|---|
| reversed_weak | default | 0.000 → 0.001 | 1.000 → 1.000 | 406,664 → 202,317 (run time 98 s → 22 s) |
| dpkg | default, tendency | 0.52 → 0.54 | 0.26 → 0.24 | 26,430 → 5,572; 35,695 → 5,563 |
| dpkg | strict | 0.006 → 0.024 | 0.089 → 0.075 | 25,915 → 5,415 |
| py_stdlib | strict | 1.000 → 1.000 | **0.120 → 0.038** | 0 → 0 |
| py_dist | strict | 1.000 → 1.000 | **0.064 → 0.020** | 0 → 0 |
| hidden-cov30, cov50 | strict | as above | | |

## Reading

- **`COVSELF 2` with `COVSOURCE 1`** is what a fix looks like:
  - every one of the decoy world's ~1,000 confident errors is gone, in all three profiles;
  - default and tendency become exact there;
  - the only cost elsewhere is about one point of strict recall on one incomplete world.
- **Strict still answers nothing on `reversed_weak`.** Its true hidden facts are transitive `requires` chains, whose
  coverage has no trustworthy source left once the decoy is gone. Strict is now silent there instead of wrong, which
  is the trade it should make. Recovering those facts needs a better coverage estimator (`docs/DEVELOPING.md`,
  open work).
- **On its own (`COVSOURCE 0`),** the mirror test catches inverses on real code that look like laws but whose mirrors
  are contradicted, and strict loses correct answers with them (py_stdlib recall 0.12 → 0.04 at precision 1.0).
  The two fixes belong together.
- **Not yet shown:**
  - performance on unseen data: this is development data, and a fair test needs a Round 3 pre-registration and a
    new generator;
  - the asymmetric case under `COVSOURCE 0`, where the decoy's own mirror (`suggests ⇒ requires`, agreement 0.20) is
    still admitted.
