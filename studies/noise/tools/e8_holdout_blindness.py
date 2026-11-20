"""E8 (EXPLORATORY, after E6/E7): does holdout self-tuning see the benefit of denoising? company30 seeds 3-5: holdout
score vs true score of the defaults, QUARANTINE 1 and TREES 1. Writes results_holdout_blindness.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, e6_tuning as E6
out = {}
for seed in (3, 4, 5):
    obs, hid, rels, truth, stated, missing, ext, _ = E6.split("company30", seed)
    r = E6.T.tune(obs, space=[("QUARANTINE", [0, 1]), ("TREES", [0, 1])], sweeps=1, min_gain=1.0, binary=lib.VOLTEX)   # min_gain 1: score only
    row = {"holdout_default": r.baseline, "holdout": {f'{h["setting"]}={h["value"]}': h["score"] for h in r.history}}
    row["truth"] = {name: E6.test_score(obs, st, rels, stated, missing, ext, truth) for name, st in (("default", {}), ("QUARANTINE=1", {"QUARANTINE": 1}), ("TREES=1", {"TREES": 1}))}
    cor = {tuple(c[:3]) for c in hid["corrupted"]}
    row["corrupted_share_of_noisy_relation_facts"] = len(cor & stated) / len([f for f in stated if f[0] in ("is based in", "is on")])
    out[seed] = row
    print(seed, round(row["holdout_default"], 4), {k: round(v, 4) for k, v in row["holdout"].items()}, {k: round(v["f05"], 4) for k, v in row["truth"].items()}, flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_holdout_blindness.json"), "w"), indent=1)
