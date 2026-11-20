"""E9 (EXPLORATORY, after the coverage sweep): the precision collapse at coverage 0.9. Is it noise? Hidden world,
scale 1, coverage 0.9, noise 0.03 and 0.15, seeds 0-2, defaults. Writes results_coverage_cascade.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
RULE = "[? is ancestor of ?](a,b) & [? is sibling of ?](b,c) => [? is parent of ?](a,c)"
out = []
for nz in (0.03, 0.15):
    for s in (0, 1, 2):
        obs, hid = lib.world("hidden", seed=s, scale=1, coverage=0.9, noise=nz, reports=1)
        o = lib.run(obs, [])
        r = lib.score(o, obs, hid)
        acc = [l.strip() for l in o.splitlines() if l.strip().startswith("ACCEPT") and RULE in l]
        out.append({"noise": nz, "seed": s, "derived_new": r["derived_new"], "precision": r["precision"], "tendency_rule_accepted": bool(acc),
                    "rule_line": acc[0] if acc else ""})
        print(nz, s, r["derived_new"], round(r["precision"], 4), bool(acc), flush=True)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_coverage_cascade.json"), "w"), indent=1)
