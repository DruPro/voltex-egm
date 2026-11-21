# Deviations from PREREGISTRATION.md

Each change to the plan after it was hashed, with the reason. Before hashing, these harness notes already applied:

- `results_gate.jsonl` holds the single-engine gate rows twice, because the gate was rerun after the consensus arms
  were added. Both copies are identical (same answer hash).
- A pipe deadlock in `run_engine` (a long ASK list filled stdin while the engine blocked on stdout) was fixed before
  the smoke rows for S4-S6 were written. No result was produced with the deadlocked version.

## After hashing

1. **Confirmatory run interrupted and resumed** (2026-11-21). The first `run.py confirm` process stopped when the
   session ended, after 45 of 54 rows. It was restarted with the same files (sha256 checked against
   `prereg_hash.txt`). The harness skips rows already written, so no row was rerun or replaced. The resumed output
   is appended to `logs/confirm.log` after a marker line.
2. **Exploratory addition after seeing results** (2026-11-21). `results_explore.jsonl` showed consensus dropping
   318-1,055 answers per seed at 122,042 facts with 15% noise. To learn whether those drops mattered, part
   `explore2` (S1, S3, S5 at scale 32 with noise; S1, S3 at scale 64 with noise) was added to `run.py`. It is
   exploratory. `tools/run.py` therefore no longer matches its pre-registration hash; the only change is the new
   `explore2` block, and the `confirm` cells are untouched.

3. **Memory measurement correction** (2026-11-21). Per-engine peak memory read with `wait4` from inside the Python harness included the parent's high-water mark when the engine was smaller than the harness. Values were re-measured with `/usr/bin/time` from a small shell and corrected in RESULTS.md with the reported value kept alongside. No verdict changes.
