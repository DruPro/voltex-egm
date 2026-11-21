# Deviations from PREREGISTRATION.md

Before hashing (harness notes):
- The gates world generator ran out of names at 3,200 per kind (it needs 64,000 and has 58,800), so the audit sweep
  stops at 2,400 per kind. This is a limit of the test generator, not of the engine.

After hashing:
1. **Gate harness fix (E1).** The first E1 run reported 0/221 identical, because the variant's `SET CLUSTERSTREAM 1`
   prints a `[SET] CLUSTERSTREAM = 1` line that the frozen run does not (checked on `t_lineage`: it was the only
   differing line). `tools/gate.py` now drops the echo lines of B's extra settings, and only those. E1 was rerun.
   Only a one-line summary of the first run was kept (`logs/gate_E1_run1_set_echo.log`); its full output was not saved.
2. **Same echo bug in `compare.py` (E2).** The first comparison hashed outputs including the variant's
   `[SET] CLUSTERSTREAM = 1` line, so every E2 hash differed (`results_compare.jsonl`). The outputs were not saved, so
   E2 was rerun with `tools/e2_rerun.py`. It saves both raw outputs (`logs/e2/`, untracked) and compares them after
   dropping that echo line only, and reports any other differing line. The timing and memory figures for M1-M3 come
   from the first run; the echo line does not affect them.
3. **Log redaction.** `logs/audit_stages.log` held a traceback (the gates generator running out of names) with the
   absolute repository path. That path was replaced with `<repo>`; nothing else in the log was changed.

4. **Memory measurement correction** (2026-11-21). Per-engine peak memory read with `wait4` from inside the Python harness included the parent's high-water mark when the engine was smaller than the harness. Values were re-measured with `/usr/bin/time` from a small shell and corrected in RESULTS.md with the reported value kept alongside. No verdict changes.
