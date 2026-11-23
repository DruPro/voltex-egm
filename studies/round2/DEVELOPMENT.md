# Round 2: development log

Development data only: the Round 1 development worlds (`studies/capability/tools/cworlds.py`, seeds 0 to 4) and the
Round 1 confirmation real data, now development (dpkg splits 1000 to 1004). The Round 2 sealed generator
(`studies/sealed2/`) has been self-checked by its author at seeds 0 to 2. No engine has run on it, and its
confirmation seeds have not been chosen.

Owner decisions (DESIGN section 6): all four as recommended. W1 measure both, prefer W1b. W2 subject bootstrap.
Confirmation real data from this machine (C headers, time zones and services, Python `Requires-Dist`). Separate
agent for the generator; C-H1 is strict and exceeds max(2 sd, 0.005 AURC).

## W1. The coverage estimate's own reliability

Engine (opt-in, legacy byte-identical: gate 221/221 after each change below):

- `estimateCoverage()` replaces two copies of the estimator and records each relation's source: the inverse rule
  and its agreement, the median (`global`) and which relation supplied it, `refuted`, or `none`.
- **W1b, setting `COVSOURCE 1`:** a relation's estimate c is refuted when another rule concluding that relation is
  confirmed significantly more often than c allows (z > 3). A refuted estimate is not used, and it does not enter
  the median. Where a relation would have used the median and the median is refuted for it, it uses none.
- **W1a, policy field `minCoverageSourceAgreement`:** at admission, coverage from a source whose agreement is below
  the field's value is ignored, and reliability falls back to the rate.
- The new evidence-vector fields are `cov_source` and `cov_source_agree`.

### Iteration 1: refute on any excess (z > 3 above n·c)

`dev/covsrc.py`, `dev/w1_compare.py`.

- **dpkg:** the flood is gone in both flooding splits, and accepted rule counts go from 10/2/3/10/5 to 4/2/3/4/5.
  The refuted estimate had also reached, through the median, every relation without an estimate of its own.
- **`hidden` worlds:** legitimate estimates are refuted. Strict recall on hidden-cov70 falls from 0.524 to 0.092,
  and AURC gets worse on every coverage level. `dev/refute_diag.py`: chain rules there are confirmed at 1.15 to 1.2
  times the inverse-based estimate, with z of 3.4 to 9 at n of 300 to 1,700. That is missingness that is not at
  random (premises stated means a better-observed entity), not a broken estimate. dpkg's excess is 3.3 times.
- **Bug (mine):** `cov_source_agree` read 0.009 to 0.02 on `hidden`. The source was stored as an index into
  `ruleList`, which is reordered after estimation. The fix stores the source's agreement when the estimate is made.
- **W1a cannot fix dpkg** with `minCoverageSourceAgreement 0.5` on the tendency policy, which was unchanged:
  precision 0.523, 26,890 new answers. The flood is admitted at induction, because the relaxed acceptance bar uses
  the coverage estimate, and the tendency extension admits every accepted rule. Admission is the wrong layer for
  this fault, which is the DESIGN's prediction for W1a vs W1b.

### Iteration 2: the same tolerance as acceptance, the other way

Acceptance already assumes a true rule's rate lies within `RATE_REL` (0.8) of coverage: the relaxed bar is
`RATE_REL · c`. Refutation now uses that constant symmetrically: an estimate is refuted when a rule is confirmed
significantly (z > 3) above `c / RATE_REL`. No new constant.

| world | profile | precision, COVSOURCE 0 → 1 | recall | new | AURC |
|---|---|---|---|---|---|
| dpkg (5 splits) | default | 0.523 → 0.856 | 0.260 → 0.165 | 26,890 → 342 | 0.441 → 0.090 |
| dpkg | tendency | 0.522 → 0.856 | 0.255 → 0.165 | 36,147 → 342 | 0.441 → 0.078 |
| dpkg | strict | 0.006 → undef. (abstains) | 0.089 → 0 | 26,072 → 0 | 0.993 → undef. |
| every other development world, default, strict and tendency | | identical | identical | identical | identical |

Files: `dev/w1_iter2_hidden_dpkg.json`, `dev/w1_iter2_rest.json`. Source agreement after the bug fix: about 0.72 to
0.77 on `hidden`, about 0.2 on dpkg.

Reading: W1b is the fix, in the layer that owns the fault. With it, the dpkg instability across splits disappears,
and nothing else on development data changes. Its cost is dpkg recall. Some facts in the flood were true:
transitive `depends on` really holds about a third of the time. The engine now answers far less there and is right
86% of the time. Strict abstaining on dpkg is the C-H2 shape Round 1 asked for (no confident wrong answers), but it
gives recall 0; whether that is acceptable is a pre-registration question, not a development one. W1a stays as a
reported field and an available policy threshold. It is not adopted as the fix.

Open for the profile run: the matched settings (TREES, CHAIN 3, CONDITIONS, DEPTH 0) with `COVSOURCE 1`.
