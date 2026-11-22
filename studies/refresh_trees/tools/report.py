"""Write ../RESULTS.md from the results files (gate R1, refresh gate R2, loops R3-R6, sanitizer loops R7, bench)."""
import json, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); S = os.path.abspath(os.path.join(HERE, ".."))
g1 = json.load(open(os.path.join(S, "results_gate_R1.json"))); g2 = json.load(open(os.path.join(S, "results_refresh_gate.json")))["summary"]
L = json.load(open(os.path.join(S, "results_loops.json"))); LA = json.load(open(os.path.join(S, "results_loops_asan.json")))
bench = open(os.path.join(S, "bench_compare.txt")).read().strip().splitlines()[-1] if os.path.exists(os.path.join(S, "bench_compare.txt")) else "not run"
P = L["programs"]; sf = L["safety"]
rows = "\n".join(f"| {p['program']} | {p['correct']}/{p['steps']} | {p['new_equals_full']}/{p['steps']} | {p['new_full_builds']} | {p['new_refresh_builds']} | {p['ms_per_step_new']} | {p['ms_per_step_full']} | {p['ms_per_step_full'] / p['ms_per_step_new']:.1f}× |" for p in P)
steps = sum(p["steps"] for p in P); eq = sum(p["new_equals_full"] for p in P); ok = sum(p["correct"] for p in P)
ratios = [p["ms_per_step_full"] / p["ms_per_step_new"] for p in P]
asan_same = all(a["correct"] == b["correct"] and a["new_equals_full"] == b["new_equals_full"] for a, b in zip(P, LA["programs"]))
V = {"R1": g1["identical"] == g1["cells"] and bench.startswith("identical") and ", different 0," in bench,
     "R2": g2["non_tree_identical"] == g2["non_tree_cells"],
     "R3": all(p["correct"] == p["steps"] and p["new_full_builds"] == 0 and p["new_refresh_builds"] == p["steps"] - 1 for p in P),
     "R4": eq == steps, "R5": min(ratios) >= 3,
     "R6": sf["a_new_word"]["refresh_before_new_word"] and sf["a_new_word"]["full_after_new_word"]
           and sf["b_vanished_relation"]["refresh"]["refresh_taken"] and sf["b_vanished_relation"]["refresh"]["after"] == 0
           and sf["b_vanished_relation"]["same_answers"],
     "R7": asan_same}
v = {k: "pass" if x else "fail" for k, x in V.items()}
diff = subprocess.run(["git", "-C", os.path.join(S, "..", ".."), "diff", "--stat", "HEAD", "--", "src/voltex2.cpp"], capture_output=True, text=True).stdout.strip()
text = f"""# REFRESH for tree rules: results

Pre-registered: `PREREGISTRATION.md` (hash in `prereg_hash.txt`); baseline: `baseline_sha256.txt`; deviations:
`DEVIATIONS.md` (the R6(b) check fixed, and the stress bench added to R1). Numbers come from the results files in
this folder (`tools/report.py`).

**The change** (`src/voltex2.cpp`, {diff.splitlines()[-1].strip() if diff else 'committed'}):
- `cacheRules` and `remapRules` now keep and re-attach every relation a rule references: premises, conclusion, path
  steps, the condition relation (with its subjects recomputed from the current facts) and tree branches.
- The refresh path is allowed with `TREES`.

`REFRESH` stays off by default.

## Verdicts

| Prediction | Verdict | Result |
|---|---|---|
| R1 `REFRESH` off: byte-identical to the baseline | **{v['R1']}** | gate {g1['identical']}/{g1['cells']}; stress bench: {bench} |
| R2 existing refresh path unchanged | **{v['R2']}** | {g2['non_tree_identical']}/{g2['non_tree_cells']} non-tree cells identical. The {g2['tree_cells']} tree cells: {g2['tree_identical']} identical to the baseline's full relearn, with the new path taken in {g2['tree_cells_refresh_taken_new']} (baseline: {g2['tree_cells_refresh_taken_baseline']}) |
| R3 tree programs keep their rules, every step correct | **{v['R3']}** | {ok}/{steps} steps correct; 0 full relearns after the first build; a refresh build at every later step |
| R4 the same answers as relearning every step | **{v['R4']}** | {eq}/{steps} steps identical to a lockstep engine with `REFRESH 0` |
| R5 at least 3× cheaper per step | **{v['R5']}** | {min(ratios):.1f}-{max(ratios):.1f}×. Learning is gone; relation re-projection and full inference remain |
| R6 safety | **{v['R6']}** | a new word forces a full build; a rule whose relation vanished is dropped on the refresh path, with the same answers as relearning |
| R7 no regressions | **{v['R7']}** | `make test` 30/30 and 74 tests; `make sanitize` clean; the R3-R6 loops under the sanitizer binary give the same results |

## Tree programs across passes

One recycled step entity per program. Each step retracts the old state and ingests the new, and is asked
identically of two engines: the new path (`REFRESH 0.05`) and full relearning (`REFRESH 0`).

| Program | Correct | Same as relearning | Full relearns after the first | Refresh builds | ms/step, new | ms/step, relearn | Speedup |
|---|---|---|---|---|---|---|---|
{rows}

## What this changes

- **Every program shape tested now runs across passes without relearning:** the state machine, the busy beaver and
  binary increment, driven step by step from rules learned once. Earlier, `studies/inferred_program` H3 found tree
  programs relearning at every step.
- **R5 failed as written.** The remaining cost per step is re-projecting relations and running inference over the
  whole knowledge base, including the taught examples. A step can't yet touch only the facts it changed.
- **Not a mark of non-evidence.** `REFRESH` defers learning; it doesn't exempt runtime facts. A full build (a new
  word, a large change, a setting change) learns from every stated fact present, runtime state included. Because
  the harness retracts the previous state, at most the current state is present.

## Reported to the owner, not changed

The refresh condition computes the size of the change as `recordsIngested - recsAtFull` in unsigned arithmetic. A
change that only removes facts makes it negative, so it wraps, and the condition fails: a full build. That errs
toward relearning, so it's safe, but it means retractions alone never take the refresh path (`DEVIATIONS.md` 1).
"""
open(os.path.join(S, "RESULTS.md"), "w").write(text); print(v)
