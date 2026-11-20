# Deviations from the pre-registration

Pre-registration: `PREREGISTRATION.md`, sha256 389bd9c3…, 2026-11-20T19:24:33Z. Engine source at registration:
sha256 547a8ab2… (`prereg_hash.txt`).

## D1. VOTE: "repeated reports" judged by subjects, not by facts (before any VOTE run)

The registered test (a) required at least half of a relation's *facts* to be reported 2+ times. While writing the SDK
test world `tests/worlds.staff` (not a study world), VOTE never fired there at 25% noise with 3 reports. Each person's
wrong reports are mostly reported once, so under noise most distinct facts are single reports even though every
subject was reported 3 times. Changed to: at least half of a relation's *subjects* have a value reported 2+ times.
With one report per fact this is still never met, so H4(b) is unaffected. No VOTE result had been produced. Engine
source after D1: sha256 e2b1eee4….

## D2. REPLICATE: unbalanced half split fixed (REPLICATE rows rerun)

The registered split used the top bit of the FNV-1a hash of a name. For short, similar names it is badly unbalanced.
In the remainders test world (n0 ... n89), half A held 20 of the 22 known subjects and half B held 2, so a true law was
rejected. Found while writing the SDK tests, after the E1-E3 grid had started.

Fix: a 64-bit finalizer (murmur3 fmix64) after FNV-1a, then the low bit. Balance after the fix: company 250/246,
hidden 258/268, gates 1957/2043, remainders 46/44 subjects.

All grid rows with REPLICATE on (R, RQ, TR, TRQ) produced before the fix were moved to
`superseded_grid_*_replicate_unbalanced_split.jsonl` (149 rows) and rerun with the fixed engine. Rows with REPLICATE
off are unaffected: 14 sampled rows rerun with the fixed engine gave identical counts. Raw logs of the stopped run:
`logs/grid_*_run1_stopped.log`. Engine source after D2 is recorded in `prereg_hash.txt` (appended).

## D3. Harness fixes (no result changed)

- `e5_side_effects.py`, first run: the gate comparison stripped `[CONFIG]` lines but not the `[SET] X = 1` echo, so
  every switch "changed" all 22 datasets. Fixed to strip `[SET]` lines too and rerun. The first log is kept as
  `logs/side_effects_run1_set_line_bug.log`. Its tree-gate, adder, lineage and harvest numbers do not depend on the bug.
- `e6_tuning.py`, first run: `from egm import tune` imported the function, not the module, and crashed before any
  result was written. Fixed and restarted.
