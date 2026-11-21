# Deviations from PREREGISTRATION.md

## 1. Bench bug: the temp path of the knowledge base reached the compared output (2026-11-21, after the first C1 run)

**What happened.** `LOAD` of a knowledge base with non-default settings prints `[CONFIG] restored from <path>`. Every
cell runs in its own temporary directory, so this line differed between any two runs, of any binary. All 198 cells
with a non-default setting differed for that reason alone; all 56 cells with defaults (no `.cfg` file) were identical.
Checked on `t_remainders|trees|full`: the only differing line was that path.

**Fix.** `clean()` replaces the path after "restored from" / "saved to" with `KB`. Nothing else in the criterion
changes. Cells with settings are rerun on both binaries (`BENCH_SETTINGS_ONLY=1`, files `runs/base_s.jsonl` and
`runs/c1_s.jsonl`), and H1 is judged on those hashes, plus the first runs' hashes for the default-settings cells.
Timings (H3-H5) come from the first runs, which the bug did not affect.
