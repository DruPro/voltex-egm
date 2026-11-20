"""Exp 0: is the completeness estimate accurate? Compare Voltex's estimate with the true observed fraction per relation."""
import json, statistics as st
from harness import *
rows = []
for seed in range(5):
    for cfg in [0.3, 0.5, 0.7, "nu"]:
        w = world(seed, None if cfg == "nu" else cfg, nonuniform=cfg == "nu")
        out = run(EXP, w["path"], sets=["COV 1"])
        _, _, _, _, cov = parse_out(out, w["preds"])
        truth = true_observed_rate(w)
        per = [(p, cov[p], truth[p]) for p in cov if p != "global" and p in truth]
        glob_err = abs(cov["global"] - st.mean(truth.values())) if cov.get("global", -1) > 0 else None
        rows.append({"seed": seed, "cfg": str(cfg), "global_est": cov.get("global"), "true_mean": round(st.mean(truth.values()), 3),
                     "per_relation": [(p, e, round(t, 3)) for p, e, t in per],
                     "per_rel_abs_err": round(st.mean(abs(e - t) for _, e, t in per), 3) if per else None,
                     "relations_with_estimate": len(per), "relations_total": len(truth)})
json.dump(rows, open("results_exp0.json", "w"), indent=1)
for cfg in ["0.3", "0.5", "0.7", "nu"]:
    R = [r for r in rows if r["cfg"] == cfg]
    print(f"coverage {cfg:>4}: global estimate {st.mean(r['global_est'] for r in R):.3f} (true mean {st.mean(r['true_mean'] for r in R):.3f}) | "
          f"per-relation |error| {st.mean(r['per_rel_abs_err'] for r in R):.3f} | relations with own estimate {st.mean(r['relations_with_estimate'] for r in R):.1f} of {R[0]['relations_total']}")
print("non-uniform example (relation, estimate, true):", [r for r in rows if r["cfg"] == "nu"][0]["per_relation"])
