# Deviations

## 1. R6(b): the check was fixed, the prediction wasn't (after the first run)

The first run of R6(b) retracted one fact of a 3-fact relation and nothing else. Neither engine took the refresh
path, so the check didn't exercise what R6 is about (a rule whose relation vanishes, on the refresh path).

The reason is an existing quirk in the refresh condition, unrelated to this change. The size of the change is
`recordsIngested - recsAtFull`, in unsigned 64-bit arithmetic. A change that only removes facts makes it negative,
so it wraps to a huge number, and the condition always fails: a full build. That is safe, since it errs toward
relearning. It is reported to the owner, not changed (out of scope).

The corrected check retracts the fact and ingests one fact of existing words, so the net change is 0 and the
refresh path is eligible. The prediction is unchanged.

## 2. The stress bench was added to R1 (after the gate, before the write-up)

`docs/EVALUATION.md` §7 asks for the stress bench as well as the gate when a change is off. The pre-registration
listed only the gate. The bench was run on the new binary and compared with the run recorded earlier the same day
on the unchanged engine (`studies/eval/validation/bench_main.jsonl`). This adds a check; no prediction changed.
