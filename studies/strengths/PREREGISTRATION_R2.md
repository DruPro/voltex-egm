# Strengths study, round 2

Status: pre-registered after round 1 and before any round 2 run. Hash in `prereg_hash.txt`. Why: DEVIATIONS.md,
entry 1.

- **Data:** `tools/extract.py --r2`, giving 65,679 stated facts and 27,398 words. Round 1 plus `is a base of`
  (1,643) and `is first argument of` (12,222); the target `binds` is now `is bound to`.
- **Hidden facts and truth:** the same 5,901 hidden facts, scored the same way.
- **Base settings:** `MAXWORDS 28500`.
- **Runs:** the same seven as round 1:
  - `default`;
  - `depth1`, `depth2`, `depth0`;
  - `chain3`;
  - `trees`;
  - `full` (`TREES 1`, `CHAIN 3`, `DEPTH 0`).
- **Predictions:** P1-P5 exactly as in `PREREGISTRATION.md`, with `binds` read as `is bound to`.
- **One addition, P6:** in round 2, recall on `is a subclass of` rises from `depth1` to `depth0` by at least 0.10.
  Hidden classes whose parents are also hidden need more than one round.
