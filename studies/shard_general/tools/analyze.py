"""Verdicts G1-G4 from results_confirm.jsonl. Writes results_verdicts.json and prints a table. Usage: python3 analyze.py"""
import collections, json, os, statistics
STUDY = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = [json.loads(l) for l in open(os.path.join(STUDY, "results_confirm.jsonl"))]
single = {r["tag"]: r for r in R if r["arm"] == "single"}
runs = [r for r in R if r["arm"] != "single"]


def wkey(r):
    p = r["params"]
    return r["world"] + ("_noise" if p.get("noise") else "") if r["world"] == "company" else r["world"]


def match(r):
    b = single.get(r["tag"])
    if not b or not b.get("completed") or not r.get("completed"): return None
    return r["precision"] >= b["precision"] - 0.001 and r["recall"] >= 0.99 * b["recall"]


for r in runs: r["match"] = match(r)
A = [r for r in runs if r["arm"] == "A"]
V = {}
V["G1"] = all(r["match"] for r in A) and len(A) == 36
cells = collections.defaultdict(lambda: collections.defaultdict(list))
for r in runs: cells[(wkey(r), r["n"])][r["arm"]].append(r)
V["G2"] = all(statistics.mean(x["jaccard_vs_single"] for x in c["A"]) >= statistics.mean(x["jaccard_vs_single"] for x in c["R"])
              for c in cells.values()) and len(cells) == 12
U = {(r["tag"], r["n"]): r for r in runs if r["arm"] == "U"}
V["G3"] = all(r["match"] for r in A if (r["tag"], r["n"]) in U and U[(r["tag"], r["n"])]["match"])
V["G4"] = all(r["match"] for r in A if r["world"] == "realcode") and sum(1 for r in A if r["world"] == "realcode") == 6
rows = []
for (w, n), c in sorted(cells.items()):
    for arm in ("A", "R", "U"):
        xs = c.get(arm)
        if not xs: continue
        m = lambda k: round(statistics.mean(x[k] for x in xs), 4)
        b = [single[x["tag"]] for x in xs]
        rows.append(dict(world=w, n=n, arm=arm, match=f"{sum(1 for x in xs if x['match'])}/{len(xs)}",
                         identical=f"{sum(1 for x in xs if x['identical_to_single'])}/{len(xs)}",
                         precision=m("precision"), single_precision=round(statistics.mean(x["precision"] for x in b), 4),
                         recall=m("recall"), single_recall=round(statistics.mean(x["recall"] for x in b), 4),
                         jaccard=m("jaccard_vs_single"), missing=m("missing_vs_single"), extra=m("extra_vs_single"),
                         duplication=m("duplication"), assigned=(m("assigned_share") if xs[0]["assigned_share"] is not None else None),
                         dropped=m("consensus_dropped"), engine_s=m("engine_seconds"),
                         single_cpu=round(statistics.mean(x["cpu"] for x in b), 2), single_rss=round(statistics.mean(x["rss_mb"] for x in b), 1),
                         warnings=sum(len(x["warnings"]) for x in xs)))
json.dump({"verdicts": V, "rows": rows}, open(os.path.join(STUDY, "results_verdicts.json"), "w"), indent=1)
for k, v in V.items(): print(k, "PASS" if v else "FAIL")
for r in rows:
    print(f"{r['world']:14s} n{r['n']} {r['arm']}  match {r['match']}  ident {r['identical']}  P {r['precision']} (1 eng {r['single_precision']})  "
          f"R {r['recall']} (1 eng {r['single_recall']})  J {r['jaccard']}  miss {r['missing']} extra {r['extra']}  dup {r['duplication']}  "
          f"asg {r['assigned']}  drop {r['dropped']}  warn {r['warnings']}")
