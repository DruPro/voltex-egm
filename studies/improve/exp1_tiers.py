"""Exp 1: law vs tendency tiers. (a) calibration of estimated reliability vs true confidence, (b) precision by tier,
(c) contradiction detection when only law-tier rules may vote. Baseline = COV 2 (the conservative coverage fix)."""
import json, statistics as st, collections
from harness import *
SYSTEMS = {"COV2": ["COV 2"], "COV2+TIERS": ["COV 2", "TIERS 1"], "COV2+distinct-rules": ["COV 2", "TIERS 2"]}
rows, calib = [], []
for seed in range(5):
    for cfg in [0.3, 0.5, 0.7, "nu"]:
        w = world(seed, None if cfg == "nu" else cfg, nonuniform=cfg == "nu")
        truth = {(p, a, b) for p, fs in w["T"].items() for a, b in map(tuple, fs)}
        for name, sets in SYSTEMS.items():
            out = run(EXP, w["path"], sets=sets, log=f"logs/exp1_{name.replace(' ', '_')}_{w['tag']}.log")
            rules, derived, tiers, conflicts, _ = parse_out(out, w["preds"])
            ev = evaluate(derived, w["observed"], w["info"], w["T"], w["oracle"], w["preds"], rules, conflicts, seed)
            obs = set(w["observed"]); d = derived - obs
            law = {f for f in d if tiers.get(f) == "law"}; ten = d - law
            heldout = {f for f in truth - obs if f[1] not in w["info"]["unseen"]}
            row = {"cfg": str(cfg), "seed": seed, "system": name, "precision_all": ev["precision"],
                   "law_n": len(law), "law_precision": len(law & truth) / len(law) if law else None,
                   "tendency_n": len(ten), "tendency_precision": len(ten & truth) / len(ten) if ten else None,
                   "recall_law_only": len(law & heldout) / len(heldout), "recall_all": ev["recall"],
                   "conflict_recall": ev["contradictions"]["detection_recall"], "conflict_precision": ev["contradictions"]["flag_precision"],
                   "flags": ev["contradictions"]["flagged"]}
            rows.append(row)
            if name == "COV2+TIERS":
                for x in ev["rules"]["list"]:
                    if x.get("rel") is not None and x["true_conf"] is not None:
                        calib.append({"cfg": str(cfg), "rule": f"{x['type']} {x['r1']}|{x['r2']}=>{x['r3']}", "rel": x["rel"], "true": x["true_conf"], "tier": x["tier"]})
json.dump({"rows": rows, "calibration": calib}, open("results_exp1.json", "w"), indent=1)
def ms(xs):
    xs = [x for x in xs if x is not None]
    return f"{st.mean(xs):.3f}" if xs else "n/a"
print("(a) calibration of accepted rules (estimated reliability vs true confidence in the hidden world)")
law_true = [c for c in calib if c["true"] >= 0.99]; nonlaw = [c for c in calib if c["true"] < 0.95]
print(f"   true laws: {len(law_true)} rule-instances, labelled law {sum(c['tier'] == 'law' for c in law_true)}  | "
      f"true non-laws: {len(nonlaw)}, labelled law {sum(c['tier'] == 'law' for c in nonlaw)}")
print(f"   mean |estimated - true|: laws {st.mean(abs(c['rel'] - c['true']) for c in law_true):.3f}, non-laws {st.mean(abs(c['rel'] - c['true']) for c in nonlaw):.3f}")
print("   non-laws labelled law:", collections.Counter(c["rule"] for c in nonlaw if c["tier"] == "law"))
print("   true laws labelled tendency:", collections.Counter(c["rule"] for c in law_true if c["tier"] != "law"))
print("\n(b,c) by world and system")
print(f"{'world':5} {'system':18} {'P all':>7} {'law facts':>9} {'P law':>7} {'tend facts':>10} {'P tend':>7} {'R law-only':>10} {'R all':>7} {'conflict R':>10} {'conflict P':>10} {'flags':>6}")
for cfg in ["0.3", "0.5", "0.7", "nu"]:
    for name in SYSTEMS:
        R = [r for r in rows if r["cfg"] == cfg and r["system"] == name]
        print(f"{cfg:5} {name:18} {ms([r['precision_all'] for r in R]):>7} {ms([r['law_n'] for r in R]):>9} {ms([r['law_precision'] for r in R]):>7} "
              f"{ms([r['tendency_n'] for r in R]):>10} {ms([r['tendency_precision'] for r in R]):>7} {ms([r['recall_law_only'] for r in R]):>10} "
              f"{ms([r['recall_all'] for r in R]):>7} {ms([r['conflict_recall'] for r in R]):>10} {ms([r['conflict_precision'] for r in R]):>10} {ms([r['flags'] for r in R]):>6}")
