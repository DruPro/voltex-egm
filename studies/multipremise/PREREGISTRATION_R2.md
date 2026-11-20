# Round 2: fixes motivated by round 1's diagnosed failures

Round 1 (PREREGISTRATION.md, frozen binary voltex2_r1) results: H1a pass, H1b FAIL (a 4-step
relation was also learned at CHAIN 3, by composing a learned 3-step relation with a 2-step
rule), H1c pass, H2 FAIL (CHAIN 3 mean precision −0.024; CHAIN 4 −0.238, worst run 0.017),
H3 pass, H4 FAIL (harvest wrong −63%, harvest correct −44%), H5 pass.

Diagnoses (exploratory, from round 1's logs):
- H2: path rules with weak evidence (rates 0.19–0.50, k as low as 5) passed because the
  coverage correction relaxed the rate bar (to 0.8 × 0.22) and inflated their reliability to
  "law" (rate / coverage, capped at 1). That correction was validated only on two-premise
  rules. Promoted to law, the rules fed each other across rounds.
- H4: the true condition {farmer, miner} was found with z = 8–10 in every 70% run but was
  rejected in run s3_c70 by criterion (c), because people whose profession was never observed
  were counted as "outside" the group. Missing was treated as false. Separately, one company
  run adopted a condition naming 26 managers: a memorized list, not a group.

## Changes (only these two, both behind the same switches as round 1)

- **F1 (CHAIN ≥ 3).** Path rules are scored without the coverage correction: the rate bar is
  the shipped RATE_MIN (0.4), never relaxed, and reliability is the uncorrected known-answer
  agreement (one-value relations) or rate (others). Two-premise rules are unchanged.
- **F2 (CONDITIONS 1).** (i) Subjects with no observed value in Q are neither inside nor
  outside: they are excluded from the condition test, and a conditional rule does not fire
  for them. (ii) A condition must restrict: K may name at most half of Q's eligible values
  (values held by at least 5 chain subjects).

## Predictions

- **R2-H1.** Lineage world: CHAIN 3 and CHAIN 4 still infer 1,800/1,800 great-grandparent and
  1,200/1,200 great-great-grandparent links for unseen families, 0 wrong.
- **R2-H2.** Hidden world, 15 runs: CHAIN 3 and CHAIN 4 each lower mean precision by at most
  0.01 versus the shipped engine, and no single run by more than 0.05. Recall does not fall.
- **R2-H3.** Company world: precision per dataset not below the shipped engine; no adopted
  condition names more than half of its relation's eligible values.
- **R2-H4.** Hidden world: CONDITIONS lowers wrong "harvests" facts by at least 80% (943 →
  at most 189) and overall mean precision is at least round 1's 0.9705. Correct harvests will
  still be lost for people whose profession was never observed (an information limit, since
  the condition cannot be checked for them); prediction: at least 80% of lost correct
  harvests belong to such people. The round-1 threshold "correct harvests fall by at most
  10%" is not re-tested: it is incompatible with an open world and was a design error.
- **R2-H5.** The four unchanged worlds give round 1's results with all options on.
- **Gate.** All switches at default: byte-identical to frozen 2.2.1 on 22 datasets.
