# Reliability basis: saying how each reliability was obtained

**Problem** (`studies/round2/CONFIRMATION.md`): an inverse rule can be its relation's own coverage source. Its
reliability is then rate / rate = 1.0, which is an assumption that it is a law, reported as if it were a
measurement. Strict trusted it, and on Round 2's decoy world admitted a rule with agreement 0.14.

**Why not detect the bad ones.** From its own statistics, a true law whose facts are 30% stated is indistinguishable
from a rule that is right 30% of the time:

- true laws in `hidden-cov30` have agreement 0.47;
- the real decoy in dpkg has 0.22.

A detector (`COVSELF`, branch `round3-covself`, parked) can only use side evidence when it happens to exist. On real
Python code it refuted true laws. Self-sourcing itself is common (21 of 140 accepted rules across every dataset),
and nearly always correct: harmful in one real case (dpkg).

**What was built instead (general, no new thresholds):**

- Every rule reports `rel_basis`, how its reliability was obtained:

  | basis | meaning |
  |---|---|
  | `agreement` | measured from known answers |
  | `inverse` | rate / coverage, with the coverage estimated from a different rule |
  | `global` | rate / coverage, with the coverage borrowed from other relations' median |
  | `self` | the rule is its own coverage source: assumed |
  | `rate` | raw rate, no coverage estimate |

- A policy field, `thresholds.reliabilityBasis`, lists the bases a stratum accepts. The default is all of them, so
  nothing changes unless you ask.
- Built-in policies are unchanged (frozen). Legacy output: gate 204/221, the same as before this change (the other
  17 are the known `[CONFIG]` notice lines).

**A finding the label made visible:** on the decoy world, the transitive rules have basis `global`. Their coverage
is borrowed through the median from the decoy's self-made estimate, so the assumption propagates. A single
"self-sourced" flag would have missed this.

## What refusing assumed bases does to strict (`measure.py`, `REPORT.md`; development data, 210 world runs)

Variants:

- `strict`: as shipped
- `no-self`: refuses `self`
- `measured`: refuses `self` and `global`

| world | strict | no-self | measured |
|---|---|---|---|
| Round 2 decoy world, COVSOURCE 1 | 948 wrong, recall 0 | 0 wrong | 0 wrong |
| Round 2 decoy world, COVSOURCE 0 | 406,664 wrong | 202,317 wrong | 0 wrong |
| dpkg, COVSOURCE 0 | precision 0.006, 25,915 wrong | 0.024, 5,415 wrong | 0.024, 5,415 wrong |
| Round 1 `inverse`, `symmetric` (true laws) | precision 1.0, recall 1.0 | **recall 0** | **recall 0** |
| company (dev) | recall 0.50 | 0.28 | 0.28 |
| hidden-cov50 (dev) | recall 0.46 | 0.30 | 0.30 |
| Python stdlib (real) | precision 1.0, recall 0.12 | 1.0, 0.04 | 1.0, 0.04 |

Totals over every world set:

| COVSOURCE | strict | no-self | measured |
|---|---|---|---|
| 0: wrong answers | 432,776 | 207,929 | 5,612 |
| 0: worlds with recall > 0 | 24 | 22 | 21 |
| 1: wrong answers | 1,145 | 197 | 197 |
| 1: worlds with recall > 0 | 20 | 18 | 18 |

**Reading:** refusing assumed reliability removes most of strict's confident errors, and it also removes true laws
that have only themselves to vouch for them. That is a real trade with no right answer for every use, which is why
it is a policy field, not a change to strict. Use it when acting on a wrong answer is expensive. Keep the default
when missing true answers is.
