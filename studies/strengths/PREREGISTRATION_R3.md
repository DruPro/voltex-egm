# Strengths study, round 3

Status: pre-registered after round 2 and before any round 3 run. Hash in `prereg_hash.txt`. Why: DEVIATIONS.md,
entry 2.

- **Data, hidden facts and scoring:** as in round 2 (`obs_r2`).
- **Settings:** `MAXWORDS 28500` and `TENDENCYSTEPS 0`, added to every run.
- **Runs:** the same seven, written to `results_r3/`.
- **Predictions:** P1-P6 as before. In addition:
  - **P7:** in `full`, precision is at least 0.99 on each target relation, and no fact in a non-target relation is
    derived;
  - **P8:** in `full`, recall is at least 0.95 on each target relation.
