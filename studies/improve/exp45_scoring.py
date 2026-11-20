"""Exp 4-5: coverage-aware acceptance (COV) and the representativeness check for partial-completeness scoring (REP).
Systems: frozen (no switches), COV, REP, COV+REP. Worlds: blind world at 30/50/70% and non-uniform coverage, 5 seeds each."""
import json, statistics as st, collections
from harness import *
SYSTEMS = {"frozen": (FROZEN, []), "COV": (EXP, ["COV 1"]), "COV-lower": (EXP, ["COV 2"]), "REP": (EXP, ["REP 1"])}
rows = []
for seed in range(5):
    for cfg in [0.3, 0.5, 0.7, "nu"]:
        w = world(seed, None if cfg == "nu" else cfg, nonuniform=cfg == "nu")
        for name, (b, sets) in SYSTEMS.items():
            out = run(b, w["path"], sets=sets, log=f"logs/exp45_{name}_{w['tag']}.log")
            rules, derived, _, conflicts, _ = parse_out(out, w["preds"])
            ev = evaluate(derived, w["observed"], w["info"], w["T"], w["oracle"], w["preds"], rules, conflicts, seed)
            pp = ev["per_predicate"]
            rows.append({"seed": seed, "cfg": str(cfg), "system": name, "precision": ev["precision"], "recall": ev["recall"],
                         "recall_derivable": ev["recall_on_derivable"], "derived": ev["derived"], "wrong": ev["wrong"],
                         "rules": ev["rules"]["accepted"], "valid_rules": ev["rules"]["valid(true_conf>=0.9)"],
                         "designed_found": len(ev["rules"]["designed_true_found"]),
                         "harvest_wrong": pp["harvests"]["wrong"], "decoys": ev["rules"]["decoys_accepted"],
                         "invalid_rules": sorted(f"{x['r1']}|{x['r2']}=>{x['r3']}" for x in ev["rules"]["list"] if (x["true_conf"] or 0) < 0.9)})
json.dump(rows, open("results_exp45.json", "w"), indent=1)

def ms(xs):
    xs = [x for x in xs if x is not None]
    return f"{st.mean(xs):.3f}±{st.stdev(xs):.3f}" if len(xs) > 1 else (f"{xs[0]:.3f}" if xs else "n/a")
print(f"{'world':6} {'system':8} {'precision':>13} {'recall(all)':>13} {'recall(deriv)':>13} {'rules':>10} {'valid':>10} {'wrong facts':>12} {'harvest wrong':>13}")
for cfg in ["0.3", "0.5", "0.7", "nu"]:
    for name in SYSTEMS:
        R = [r for r in rows if r["cfg"] == cfg and r["system"] == name]
        print(f"{cfg:6} {name:8} {ms([r['precision'] for r in R]):>13} {ms([r['recall'] for r in R]):>13} {ms([r['recall_derivable'] for r in R]):>13} "
              f"{ms([r['rules'] for r in R]):>10} {ms([r['valid_rules'] for r in R]):>10} {ms([r['wrong'] for r in R]):>12} {sum(r['harvest_wrong'] for r in R):>13}")
inv = collections.Counter()
for r in rows:
    for x in r["invalid_rules"]: inv[(r["system"], x)] += 1
print("\ninvalid rules accepted (runs out of 20):")
for name in SYSTEMS:
    print(" ", name, dict(sorted(((k[1], v) for k, v in inv.items() if k[0] == name), key=lambda kv: -kv[1])))
