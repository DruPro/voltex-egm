# Round 2: deviations from the pre-registration

## D1. The sealed run restarted as resumable parallel workers (logistics; results unaffected)

The pre-registered procedure runs `confirm2.py sealed` serially. Its first world (`reversed_weak`, seed 2000) took
1,009 seconds, so the serial run would have outlived the two-hour limit on a background job in this environment. It
was stopped after that first world. Its result was deleted unread: no metric was printed or opened, only the timing
line. The run was restarted as two `confirm2.py worker` processes that write one file per (world, seed) and skip
files that exist; `confirm2.py merge` assembles `results/sealed.json` and `results/real.json`.

`run_world` and every profile, setting, seed and metric are unchanged, and each run is deterministic, so the results
are the ones the serial run would have produced. The machine has 2 CPUs. (Two workers ran out of memory: D3.)

## D2. Development code after the hash (no effect on the tested engine)

After the hash and before the results: the `egm evidence` CLI command (`egm/cli.py`) and the documentation. The CLI
is not part of any tested profile; the engine binary, `egm/engine.py`, `egm/policy.py` and the harness are unchanged
from the hashed state.

## D3. Two parallel workers ran out of memory; back to one (crash rerun)

D1's two workers both started on `reversed_weak` (seeds 2000 and 2001). Each needs about 1.7 GB for the engine and
1.6 GB for the harness, and with documentation checks running alongside, the machine's 7 GB memory cgroup killed one
engine (`dmesg`: "Memory cgroup out of memory: Killed process ... (voltex2)") during `INFER ALL`. No result file had
been written by either worker. Both were stopped, and one resumable worker runs every (structure, seed) in order. The
pre-registration allows a rerun after a crash; nothing else changed. The real-data sets run after the sealed worlds,
in the same way.
