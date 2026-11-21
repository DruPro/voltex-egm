"""X1 (EXPLORATORY, after T1 failed): T1's cascade is one tendency step amplified by law-tier rules over later
rounds (CHAINS output). Does the existing DEPTH control limit it, and at what cost? Hidden, noise 0, coverage 0.5 and
0.9, seeds 0-2, DEPTH 1/2/4 (default) x TENDENCYSTEPS -1/0. Writes results_x1.json."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "noise", "tools"))
import lib
rows = []
for cv in (0.5, 0.9):
    for s in (0, 1, 2):
        obs, hid = lib.world("hidden", seed=s, scale=1, coverage=cv, noise=0.0, reports=1, contradict=0.0)
        for d in (1, 2, 4):
            for ts in (-1, 0):
                r = lib.score(lib.run(obs, [f"SET DEPTH {d}", f"SET TENDENCYSTEPS {ts}"]), obs, hid)
                rows.append({"coverage": cv, "seed": s, "depth": d, "tendencysteps": ts, **{k: r[k] for k in ("derived_new", "correct", "wrong", "precision", "recall")}})
                print(rows[-1], flush=True)
json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_x1.json"), "w"), indent=1)
