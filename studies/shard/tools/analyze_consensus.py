"""Verdicts K1-K3 for PREREGISTRATION_CONSENSUS.md from results_consensus.jsonl. Writes results_verdicts_consensus.json."""
import json, os
STUDY = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = [json.loads(l) for l in open(os.path.join(STUDY, "results_consensus.jsonl"))]
g = {(r["seed"], r["scale"], r["noise"], r["arm"]): r for r in R}
SEEDS = (3, 4, 5); CELL = {"A": (32, 0.15), "B": (64, 0.15), "C": (16, 0.15), "D": (32, 0.0)}
prec_ok = lambda s, b: s["precision"] >= b["precision"] - 0.001
match = lambda s, b: prec_ok(s, b) and s["recall"] >= 0.99 * b["recall"]
def per(cell, arm, t):
    sc, nz = CELL[cell]; return [t(g[(sd, sc, nz, arm)], g[(sd, sc, nz, "single")]) for sd in SEEDS]
V = {"K1": all(all(per(c, "S5", match)) for c in "ABC"),
     "K2": per("A", "S1", prec_ok).count(False) >= 2 and per("B", "S1", prec_ok).count(False) >= 2,
     "K3": all(per("D", "S5", lambda s, b: s["answers_sha"] == b["answers_sha"]))}
rows = []
for c, (sc, nz) in CELL.items():
    for arm in ("single", "S1", "S5"):
        for sd in SEEDS:
            r = g[(sd, sc, nz, arm)]
            rows.append(dict(cell=c, seed=sd, arm=arm, facts=r["stated"], n=r.get("n"), precision=round(r["precision"], 4),
                             recall=round(r["recall"], 4), wrong=r["wrong"], cpu=r["cpu"], rss_mb=r["rss_mb"], dropped=r.get("dropped"),
                             identical=r["answers_sha"] == g[(sd, sc, nz, "single")]["answers_sha"], completed=r["completed"]))
json.dump({"verdicts": V, "rows": rows}, open(os.path.join(STUDY, "results_verdicts_consensus.json"), "w"), indent=1)
print(V)
for r in rows: print(r)
