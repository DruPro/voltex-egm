"""Recommended combination (COV 2 + TIERS 2 [+ STALE, inert without updates]) vs frozen, all blind-world settings."""
import json, statistics as st
from harness import *
rows = []
for seed in range(5):
    for cfg in [0.3, 0.5, 0.7, "nu"]:
        w = world(seed, None if cfg == "nu" else cfg, nonuniform=cfg == "nu")
        truth = {(p, a, b) for p, fs in w["T"].items() for a, b in map(tuple, fs)}
        for name, (b, sets) in {"frozen": (FROZEN, []), "recommended": (EXP, ["COV 2", "TIERS 2", "STALE 1"])}.items():
            rules, derived, tiers, conflicts, _ = parse_out(run(b, w["path"], sets=sets, log=f"logs/combined_{name}_{w['tag']}.log"), w["preds"])
            ev = evaluate(derived, w["observed"], w["info"], w["T"], w["oracle"], w["preds"], rules, conflicts, seed)
            d = derived - set(w["observed"]); law = {f for f in d if tiers.get(f) == "law"}
            rows.append({"cfg": str(cfg), "system": name, "precision": ev["precision"], "recall_derivable": ev["recall_on_derivable"], "recall": ev["recall"],
                         "law_precision": len(law & truth) / len(law) if law else None, "law_share": len(law) / len(d) if d else None,
                         "flags": ev["contradictions"]["flagged"], "flag_precision": ev["contradictions"]["flag_precision"]})
json.dump(rows, open("results_combined.json", "w"), indent=1)
ms = lambda xs: (lambda v: f"{st.mean(v):.3f}" if v else "n/a")([x for x in xs if x is not None])
print(f"{'world':5} {'system':12} {'precision':>9} {'recall(deriv)':>13} {'recall(all)':>11} {'P law-tier':>10} {'law share':>9} {'false flags':>11}")
for cfg in ["0.3", "0.5", "0.7", "nu"]:
    for name in ("frozen", "recommended"):
        R = [r for r in rows if r["cfg"] == cfg and r["system"] == name]
        print(f"{cfg:5} {name:12} {ms([r['precision'] for r in R]):>9} {ms([r['recall_derivable'] for r in R]):>13} {ms([r['recall'] for r in R]):>11} "
              f"{ms([r['law_precision'] for r in R]):>10} {ms([r['law_share'] for r in R]):>9} {ms([r['flags'] for r in R]):>11}")
