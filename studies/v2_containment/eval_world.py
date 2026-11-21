"""Precision / recall of INFER on the synthetic world, swept over the minimum rule rate."""
import json, subprocess, sys
truth = json.load(open("data/world_truth.json"))
T = {"is in": {tuple(x) for x in truth["is in"]}, "contains": {tuple(x) for x in truth["contains"]}, "knows": {tuple(x) for x in truth["knows"]}}
held = {"is in": {tuple(x) for x in truth["heldout_is_in"]}, "contains": {tuple(x) for x in truth["heldout_contains"]}}
def run(rate):
    cmds = f"INGESTFILE data/world_train.txt\nSET RATE {rate}\nRELATIONS\nINFER ALL\nEXIT\n"
    out = subprocess.run(["./voltex2"], input=cmds, capture_output=True, text=True).stdout
    facts = [l.split("\t")[1] for l in out.splitlines() if l.startswith("FACT\t")]
    rules = [l.strip() for l in out.splitlines() if l.strip().startswith("ACCEPT")]
    per = {}
    for f in facts:
        for rel in ("is in", "contains", "knows"):
            sep = f" {rel} "
            if sep in f:
                a, b = f.split(sep); per.setdefault(rel, []).append((a.strip(), b.strip()))
    res = {"rate_min": rate, "accepted_rules": len(rules), "derived": len(facts)}
    tp = sum(1 for rel, fs in per.items() for x in fs if x in T[rel])
    res["precision"] = round(tp / len(facts), 3) if facts else None
    for rel in ("is in", "contains"):
        got = set(per.get(rel, []))
        res[f"recall_heldout_{rel.replace(' ', '_')}"] = round(len(got & held[rel]) / len(held[rel]), 3)
    res["knows_derived(false)"] = len(per.get("knows", []))
    return res, rules
rows = []
for r in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]:
    res, rules = run(r); rows.append(res)
    if r == 0.4: print("\n".join(rules))
for x in rows: print(x)
json.dump(rows, open("results_world.json", "w"), indent=1)
