# Depth study: does removing the 4-round inference cap help, and what does it cost?

Engine: voltex2 2.2.1 plus one switch, `SET DEPTH n` (default 4 = shipped behaviour; 0 = run
until a round derives nothing new). Gate before any run: default build byte-identical to the
shipped 2.2.1 binary on 22 datasets (passed, 22/22).

Conditions: DEPTH 4 (shipped) vs DEPTH 0 (fixpoint). Nothing else changes.

## Predictions

- **D1 (remainders mod 3, 5 seeds, N=90).** At DEPTH 0 the 16 unseen numbers that were more
  than 4 steps from a taught number are now computed correctly: 208 of 225 correct, still 0
  wrong. The 17 with no taught number below stay blank. Pass: exactly 208/225, 0 wrong.
- **D2 (divisibility, 5 seeds, N=150).** Unchanged: 319 of 319 derivable facts, 0 wrong.
  Transitivity over derived facts already reaches the closure within 4 rounds here.
- **D3 (blind world, 5 seeds x 3 coverages, 15 runs).** Deeper chains through accepted rules
  may also chain tendency and decoy rules further. Prediction: recall does not fall, and mean
  precision falls by at most 0.02. A larger drop would mean unlimited depth needs a per-tier
  policy (law-tier rules to fixpoint, tendencies capped). This is the test that matters.
- **D4 (cost).** Rounds used at DEPTH 0 and inference time are reported for every run. No
  pass/fail threshold; exploratory.

## Integrity

The blind world's hidden truth and evaluator are reused unchanged from the Blind World study;
the engine only sees the observation files. Results go to results_depth.json. Any change to
this plan goes in DEVIATIONS.md.
