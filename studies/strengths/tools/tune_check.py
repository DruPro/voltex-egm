"""Exploratory: can egm.tune find the settings that mattered on exact code facts?  python3 tune_check.py default|extended|api_default|api_expanded

`default` uses egm.tune's DEFAULT_SPACE. `extended` adds TENDENCYSTEPS (-1, 0), DEPTH 1 and 2, and MAXWORDS (12000,
28500), because tune() has no way to pass base settings. Input: obs_r2/facts.txt (stdlib, round 2 facts). Writes
../tune/<mode>.json.
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
from egm.tune import DEFAULT_SPACE  # noqa: E402
mode = sys.argv[1]
if mode.startswith("api_"):   # the public API after the change: egm.tune(...) and egm.tune(..., expanded=True)
    t = time.time()
    r = egm.tune(os.path.join(STUDY, "obs_r2", "facts.txt"), expanded=(mode == "api_expanded"), binary=os.path.join(ROOT, "build", "voltex2"))
    out = {"mode": mode, "settings": r.settings, "baseline": r.baseline, "tuned": r.tuned, "baseline_folds": r.baseline_folds,
           "tuned_folds": r.tuned_folds, "evaluations": r.evaluations, "wall_s": round(time.time() - t, 1), "history": r.history}
    json.dump(out, open(os.path.join(STUDY, "tune", mode + ".json"), "w"), indent=1)
    print(r.report(), f"\n{out['wall_s']} s"); sys.exit()
space = list(DEFAULT_SPACE)
if mode == "extended":
    space = [("MAXWORDS", [12000, 28500]), ("TENDENCYSTEPS", [-1, 0])] + \
            [(k, [4, 0, 1, 2]) if k == "DEPTH" else (k, v) for k, v in DEFAULT_SPACE]
t = time.time()
r = egm.tune(os.path.join(STUDY, "obs_r2", "facts.txt"), space=space, binary=os.path.join(ROOT, "build", "voltex2"))
out = {"mode": mode, "settings": r.settings, "baseline": r.baseline, "tuned": r.tuned, "baseline_folds": r.baseline_folds,
       "tuned_folds": r.tuned_folds, "evaluations": r.evaluations, "wall_s": round(time.time() - t, 1), "history": r.history}
json.dump(out, open(os.path.join(STUDY, "tune", mode + ".json"), "w"), indent=1)
print(r.report(), f"\n{out['wall_s']} s")
