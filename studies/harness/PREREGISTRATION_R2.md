# Harness study, round 2

Status: pre-registered after round 1 and before any round 2 run on seeds 0-2. Hash in `prereg_hash.txt`. Why:
`DEVIATIONS.md` 1.

## Changes

- **Step facts:** one relation per kind of output value. `w has symbol <s>`, `m has direction <d>` and
  `n has state <q>` replace `has value`. Every other fact is the same, and the harness is unchanged.
- **Examples per transition in H3 and H4:** 64, the smallest value that gave 9/9 transitions on the probe pools.
- **H2 machine curve:** k = 8, 16, 32, 64, 100.
- **H2 gate curve:** k = 2, 4, 8, 16, 32, 64, 100, 200.
- **H1:** the same as round 1, rerun.

## Predictions

H1a, H2, H3a, H3b and H4 as in `PREREGISTRATION.md`. H1b and H3c are replaced, because round 1 showed that new data
can teach true structural rules:
- **H1b'.** Rules concluding a wire's value (`has value`) are identical before and after the 10 adders are
  ingested, in every seed.
- **H3c'.** Rules concluding a step output (`has symbol`, `has direction`, `has state` of an output slot) are
  identical before and after each run.
