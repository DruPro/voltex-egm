"""Log-log growth exponents per stage from results_audit_stages.jsonl (descriptive). Usage: python3 fit.py"""
import json, math, os, collections
STUDY = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = [json.loads(l) for l in open(os.path.join(STUDY, "results_audit_stages.jsonl"))]
def slope(xs, ys):
    pts = [(math.log(x), math.log(y)) for x, y in zip(xs, ys) if x > 0 and y > 0]
    mx = sum(p[0] for p in pts) / len(pts); my = sum(p[1] for p in pts) / len(pts)
    return sum((a - mx) * (b - my) for a, b in pts) / sum((a - mx) ** 2 for a, _ in pts)
out = {}
for w in ("company", "hidden", "gates"):
    rs = sorted([r for r in R if r["world"] == w], key=lambda r: r["facts"])
    rs = [r for r in rs if r["facts"] >= (15000 if w == "company" else 0)]
    F = [r["facts"] for r in rs]; Vv = [r["vocab"] for r in rs]
    d = {"n": len(rs), "facts": [min(F), max(F)], "vocab": [min(Vv), max(Vv)], "vocab_vs_facts": slope(F, Vv)}
    for k in ("classes_ms", "relations_ms", "mining_ms", "infer_ms", "rss_mb", "cpu"):
        d[k + "_vs_facts"] = slope(F, [r[k] for r in rs])
    d["classes_ms_vs_vocab"] = slope(Vv, [r["classes_ms"] for r in rs])
    d["kept_pairs_vs_vocab"] = slope(Vv, [r["lab_rounds"][0]["kept"] for r in rs])
    d["kept_share_of_all_pairs"] = [round(r["lab_rounds"][0]["kept"] / (r["lab_rounds"][0]["K"] * (r["lab_rounds"][0]["K"] - 1) / 2), 3) for r in rs]
    d["kept_mb_share_of_peak"] = [round(r["lab_rounds"][0]["kept_mb"] / r["rss_mb"], 3) for r in rs]
    d["classes_share_of_cpu"] = [round(r["classes_ms"] / 1000 / r["cpu"], 3) for r in rs]
    d["ingest_MBps"] = [round(r["bytes"] / 1e6 / r["ingest_s"], 1) for r in rs]
    out[w] = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}
json.dump(out, open(os.path.join(STUDY, "results_fit.json"), "w"), indent=1)
for w, d in out.items():
    print(w); [print("  ", k, v) for k, v in d.items()]
