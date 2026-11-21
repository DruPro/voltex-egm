"""Verdicts for PREREGISTRATION.md, computed from results_confirm.jsonl only. Writes results_verdicts.json and prints
a table. Usage: python3 analyze.py"""
import json, os, statistics
STUDY = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = [json.loads(l) for l in open(os.path.join(STUDY, "results_confirm.jsonl"))]
SEEDS = (0, 1, 2)


def get(seed, scale, noise, arm):
    m = [r for r in R if (r["seed"], r["scale"], r["noise"], r["arm"]) == (seed, scale, noise, arm)]
    return m[-1] if m else None


def prec_ok(s, b): return s["precision"] >= b["precision"] - 0.001
def rec_ok(s, b): return s["recall"] >= 0.99 * b["recall"]
def match(s, b): return prec_ok(s, b) and rec_ok(s, b)


def per_seed(scale, noise, arm, test):
    out = []
    for sd in SEEDS:
        s, b = get(sd, scale, noise, arm), get(sd, scale, noise, "single")
        out.append(None if not (s and b and s.get("completed") and b.get("completed")) else bool(test(s, b)))
    return out


V = {}
V["H1"] = all(per_seed(32, 0.0, "S4", match))
V["H2"] = all(per_seed(16, 0.15, "S4", match))
V["H3"] = (all(per_seed(16, 0.15, "S5", prec_ok)) and per_seed(16, 0.15, "S6", prec_ok).count(False) >= 2
           and per_seed(16, 0.15, "S0", prec_ok).count(False) >= 2)
V["H4"] = per_seed(16, 0.15, "S3", prec_ok).count(False) >= 2
V["H5"] = per_seed(32, 0.0, "S5", rec_ok).count(False) >= 2 and all(per_seed(32, 0.0, "S4", rec_ok))
h6 = [get(sd, 64, 0.0, "S4") for sd in SEEDS]
V["H6"] = all(r and r["completed"] and r["rss_mb"] <= 500 and r["precision"] >= 0.999 for r in h6)
singles64 = [get(sd, 64, 0.0, "single") for sd in SEEDS]
V["H6b"] = (all(per_seed(64, 0.0, "S4", match)) if all(r and r.get("completed") for r in singles64)
            else "not applicable: one engine did not complete")
V["C1"] = all(per_seed(32, 0.0, "S4", lambda s, b: s["rss_mb"] <= 0.25 * b["rss_mb"]))
V["C2"] = all(per_seed(32, 0.0, "S4", lambda s, b: s["cpu"] <= b["cpu"]))

rows = []
for scale, noise in ((32, 0.0), (16, 0.15), (64, 0.0)):
    for arm in ["single", "S0", "S1", "S2", "S3", "S4", "S5", "S6"]:
        rs = [get(sd, scale, noise, arm) for sd in SEEDS]
        rs = [r for r in rs if r]
        if not rs: continue
        done = [r for r in rs if r.get("completed")]
        f = lambda k: (round(statistics.mean(r[k] for r in done), 4), round(statistics.pstdev(r[k] for r in done), 4)) if done else None
        rows.append(dict(scale=scale, noise=noise, arm=arm, runs=len(rs), completed=len(done), facts=rs[0].get("stated"),
                         precision=f("precision"), recall=f("recall"), wrong=f("wrong"), derived_new=f("derived_new"),
                         cpu=f("cpu"), rss_mb=f("rss_mb"), limit_lines=sum(r.get("limit_lines", 0) for r in rs),
                         match=per_seed(scale, noise, arm, match) if arm != "single" else None,
                         dropped=[r.get("dropped") for r in rs], minority=[len(r.get("rules_minority", [])) for r in rs]))
json.dump({"verdicts": V, "rows": rows}, open(os.path.join(STUDY, "results_verdicts.json"), "w"), indent=1)
for k, v in V.items(): print(f"{k:4s} {'PASS' if v is True else 'FAIL' if v is False else v}")
print()
for r in rows:
    print(f"{r['facts']:>7} n{r['noise']:<4} {r['arm']:6s} done {r['completed']}/{r['runs']}  P {r['precision']}  R {r['recall']}  "
          f"wrong {r['wrong']}  cpu {r['cpu']}  rss {r['rss_mb']}  limit {r['limit_lines']}  match {r['match']}  dropped {r['dropped']}")
