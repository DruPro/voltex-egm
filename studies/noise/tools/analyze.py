"""Compute every registered hypothesis from the results files. Writes results_verdicts.json and prints tables."""
import collections, json, os, statistics
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load(name):
    p = os.path.join(D, name)
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


grid = load("results_grid_company.jsonl") + load("results_grid_hidden.jsonl") + load("results_grid_coverage.jsonl") + load("results_grid_gates.jsonl")
vote = load("results_vote.jsonl")
V = {}


def per1000(rows, key):
    n = sum(r["derived_new"] for r in rows); return 1000 * sum(r.get(key, 0) for r in rows) / n if n else 0.0


def cell(world, config, **kw):
    out = []
    for r in grid:
        if r["world"] != world or r["config"] != config: continue
        if all(r["params"].get(k) == v for k, v in kw.items()): out.append(r)
    return out


def scale_key(world):
    return "scale"


def table():
    rows = []
    for (w, c), rs in sorted(collections.defaultdict(list, {}).items()): pass
    agg = collections.defaultdict(list)
    for r in grid:
        p = r["params"]
        k = (r["world"], p.get("scale", p.get("per_kind")), p.get("coverage", ""), p["noise"] if "noise" in p else 0, r["config"])
        agg[k].append(r)
    for k in sorted(agg, key=lambda x: (x[0], str(x[2]), x[3], x[1], x[4])):
        rs = agg[k]
        rows.append({"world": k[0], "size": k[1], "coverage": k[2], "noise": k[3], "config": k[4], "runs": len(rs),
                     "derived": statistics.mean(r["derived_new"] for r in rs), "correct": statistics.mean(r["correct"] for r in rs),
                     "wrong": statistics.mean(r["wrong"] for r in rs),
                     "precision": statistics.mean(r["precision"] for r in rs), "recall": statistics.mean(r["recall"] for r in rs),
                     "rule_err_per_1000": per1000(rs, "cause_rule"), "prop_err_per_1000": per1000(rs, "cause_propagation"),
                     "flag_hits": statistics.mean(r["flag_hits"] for r in rs), "flagged": statistics.mean(r["flagged"] for r in rs),
                     "corrupted": statistics.mean(r["corrupted"] for r in rs), "quarantined": statistics.mean(r["quarantined"] for r in rs),
                     "repl_rejected": statistics.mean(r["repl_rejected"] for r in rs), "invented": sum(r["invented_unseen"] for r in rs)})
    return rows


def h1_h3():
    res = {}
    sizes = {"company": (0.5, 4.0), "hidden": (1, 4)}
    noises = {"company": (0.15, 0.30), "hidden": (0.15, 0.30)}
    # H1a / H1b (base and T), H2c (R, TR)
    for hyp, confs in (("H1", ("base", "T")), ("H2c", ("R", "TR"))):
        checks = []
        for w in ("company", "hidden"):
            lo, hi = sizes[w]
            for nz in noises[w] + ((0.03,) if w == "hidden" else ()):
                for c in confs:
                    a = cell(w, c, scale=lo, noise=nz, **({"coverage": 0.5} if w == "hidden" else {}))
                    b = cell(w, c, scale=hi, noise=nz, **({"coverage": 0.5} if w == "hidden" else {}))
                    if not a or not b: continue
                    ra, rb = per1000(a, "cause_rule"), per1000(b, "cause_rule")
                    pa, pb = per1000(a, "cause_propagation"), per1000(b, "cause_propagation")
                    checks.append({"world": w, "noise": nz, "config": c, "rule_small": ra, "rule_large": rb, "prop_small": pa, "prop_large": pb,
                                   "a_pass": rb <= ra, "b_pass": not (pa > 0 and pb <= 0.5 * pa)})
        res[hyp] = {"checks": checks, "a_pass": all(x["a_pass"] for x in checks) if checks else None,
                    "b_pass": all(x["b_pass"] for x in checks) if checks else None}
    # H2a: TR vs T at company noise 0.30
    t = cell("company", "T", noise=0.30); tr = cell("company", "TR", noise=0.30)
    wt, wtr = sum(r["wrong"] for r in t), sum(r["wrong"] for r in tr)
    res["H2a"] = {"wrong_T": wt, "wrong_TR": wtr, "cut": 1 - wtr / wt if wt else None, "pass": bool(wt) and wtr <= 0.5 * wt}
    # H2b / H3b: noise-free worlds, correct inferences
    def clean(w):
        return {"company": dict(noise=0.0), "gates": dict(noise=0.0), "hidden": None}[w]
    h2b, h3b = [], []
    for w, pairs2, pairs3 in (("company", (("base", "R"), ("T", "TR")), (("base", "Q"), ("T", "TQ"))),
                              ("gates", (("T", "TR"),), (("T", "TQ"),))):
        for a, b in pairs2:
            ca = sum(r["correct"] for r in cell(w, a, noise=0.0)); cb = sum(r["correct"] for r in cell(w, b, noise=0.0))
            h2b.append({"world": w, "from": a, "to": b, "correct_from": ca, "correct_to": cb, "change": (cb - ca) / ca if ca else 0, "pass": ca == 0 or cb >= 0.95 * ca})
        for a, b in pairs3:
            ca = sum(r["correct"] for r in cell(w, a, noise=0.0)); cb = sum(r["correct"] for r in cell(w, b, noise=0.0))
            h3b.append({"world": w, "from": a, "to": b, "correct_from": ca, "correct_to": cb, "change": (cb - ca) / ca if ca else 0, "pass": ca == 0 or abs(cb - ca) <= 0.02 * ca})
    res["H2b"] = {"checks": h2b, "pass": all(x["pass"] for x in h2b)}
    res["H3b"] = {"checks": h3b, "pass": all(x["pass"] for x in h3b)}
    # H3a: propagation errors, Q vs base, company and hidden at 0.15 / 0.30
    h3a = []
    for w in ("company", "hidden"):
        for nz in (0.15, 0.30):
            kw = {"noise": nz, **({"coverage": 0.5} if w == "hidden" else {})}
            a = sum(r.get("cause_propagation", 0) for r in cell(w, "base", **kw)); b = sum(r.get("cause_propagation", 0) for r in cell(w, "Q", **kw))
            h3a.append({"world": w, "noise": nz, "prop_base": a, "prop_Q": b, "pass": a == 0 or b <= 0.5 * a, "vacuous": a == 0})
    res["H3a"] = {"checks": h3a, "pass": all(x["pass"] for x in h3a)}
    # H3c: precision never falls by more than 0.5 points (Q vs base, TQ vs T), per world x noise cell
    h3c = []
    for w in ("company", "hidden", "gates"):
        nzs = sorted({r["params"]["noise"] for r in grid if r["world"] == w})
        for nz in nzs:
            for a, b in (("base", "Q"), ("T", "TQ")):
                ra, rb = cell(w, a, noise=nz), cell(w, b, noise=nz)
                if not ra or not rb: continue
                pa = statistics.mean(r["precision"] for r in ra); pb = statistics.mean(r["precision"] for r in rb)
                h3c.append({"world": w, "noise": nz, "from": a, "to": b, "prec_from": pa, "prec_to": pb, "pass": pb >= pa - 0.005})
    res["H3c"] = {"checks": h3c, "pass": all(x["pass"] for x in h3c)}
    # H5: invented facts
    res["H5_invented"] = {"total_invented": sum(r["invented_unseen"] for r in grid + vote), "pass": sum(r["invented_unseen"] for r in grid + vote) == 0}
    return res


def h4():
    res = {}
    def cellv(w, c, nz, rp): return [r for r in vote if r["world"] == w and r["config"] == c and r["params"]["noise"] == nz and r["params"]["reports"] == rp]
    a = []
    for w in ("company", "hidden"):
        b0 = cellv(w, "base", 0.15, 3); v0 = cellv(w, "V", 0.15, 3)
        lb = sum(r["wrong_evidence_left"] for r in b0); lv = sum(r["wrong_evidence_left"] for r in v0)
        a.append({"world": w, "wrong_evidence_base": lb, "wrong_evidence_V": lv, "pass": lb > 0 and lv <= 0.5 * lb})
    res["H4a"] = {"checks": a, "pass": all(x["pass"] for x in a)}
    b = []
    for w in ("company", "hidden"):
        for nz in (0.15, 0.30):
            bb = {r["params"]["seed"]: r["fact_lines_hash"] for r in cellv(w, "base", nz, 1)}
            vv = {r["params"]["seed"]: r["fact_lines_hash"] for r in cellv(w, "V", nz, 1)}
            b.append({"world": w, "noise": nz, "identical_seeds": sum(bb[s] == vv.get(s) for s in bb), "of": len(bb)})
    res["H4b"] = {"checks": b, "pass": all(x["identical_seeds"] == x["of"] for x in b)}
    c, d = [], []
    for w in ("company", "hidden"):
        for nz in (0.15, 0.30):
            for rp in (1, 3, 5):
                pb = statistics.mean(r["precision"] for r in cellv(w, "base", nz, rp)); pv = statistics.mean(r["precision"] for r in cellv(w, "V", nz, rp))
                c.append({"world": w, "noise": nz, "reports": rp, "prec_base": pb, "prec_V": pv, "pass": pv >= pb - 1e-12})
            ws = [statistics.mean(r["wrong"] for r in cellv(w, "V", nz, rp)) for rp in (1, 3, 5)]
            d.append({"world": w, "noise": nz, "wrong_r1": ws[0], "wrong_r3": ws[1], "wrong_r5": ws[2], "pass": ws[2] <= ws[1] <= ws[0]})
    res["H4c"] = {"checks": c, "pass": all(x["pass"] for x in c)}
    res["H4d"] = {"checks": d, "pass": all(x["pass"] for x in d)}
    vt = collections.defaultdict(list)
    for r in vote: vt[(r["world"], r["params"]["noise"], r["params"]["reports"], r["config"])].append(r)
    res["table"] = [{"world": k[0], "noise": k[1], "reports": k[2], "config": k[3], "derived": statistics.mean(r["derived_new"] for r in v),
                     "wrong": statistics.mean(r["wrong"] for r in v), "precision": statistics.mean(r["precision"] for r in v),
                     "recall": statistics.mean(r["recall"] for r in v), "wrong_evidence_left": statistics.mean(r["wrong_evidence_left"] for r in v),
                     "wrong_evidence_stated": statistics.mean(r["wrong_evidence_stated"] for r in v), "true_removed": statistics.mean(r["true_removed"] for r in v)}
                    for k, v in sorted(vt.items())]
    return res


def h6():
    p = os.path.join(D, "results_tuning.json")
    if not os.path.exists(p): return {}
    t = json.load(open(p)); runs = t["runs"]
    worlds = sorted({r["world"] for r in runs.values()})
    per = {}
    for w in worlds:
        rs = [r for r in runs.values() if r["world"] == w]
        per[w] = {c: statistics.mean(r[c]["f05"] for r in rs) for c in ("default", "self", "ext", "oracle")}
        per[w].update({c + "_prec": statistics.mean(r[c]["precision"] for r in rs) for c in ("default", "self", "ext", "oracle")})
        per[w].update({c + "_recall": statistics.mean(r[c]["recall"] for r in rs) for c in ("default", "self", "ext", "oracle")})
        per[w]["self_settings"] = [r["self_settings"] for r in rs]; per[w]["oracle_settings"] = [r["oracle_settings"] for r in rs]
        per[w]["ext_settings"] = [r["ext_settings"] for r in rs]
    wins = [w for w in worlds if per[w]["self"] > per[w]["default"]]
    prec_ok = all(per[w]["self_prec"] >= per[w]["default_prec"] - 0.01 for w in worlds)
    gains = [(per[w]["self"] - per[w]["default"]) / (per[w]["oracle"] - per[w]["default"]) for w in worlds if per[w]["oracle"] > per[w]["default"] + 1e-9]
    within = t.get("transfer_within", [])
    kept = []
    for x in within:
        own = x["own_self_f05"] - x["default_f05"]
        if own > 1e-9: kept.append((x["f05"] - x["default_f05"]) / own)
    leaks = sum(len(r["hidden_files_opened_by_self_tuner"]) for r in runs.values())
    return {"per_world": per, "H6a": {"wins": wins, "of": len(worlds), "precision_ok": prec_ok, "pass": len(wins) >= 4 and prec_ok},
            "H6b": {"share_of_oracle_gain_per_world": gains, "mean": statistics.mean(gains) if gains else None, "pass": bool(gains) and statistics.mean(gains) >= 0.5},
            "H6c": {"share_kept": kept, "mean": statistics.mean(kept) if kept else None, "pass": bool(kept) and statistics.mean(kept) >= 0.5},
            "H6d_cross": t.get("transfer_cross", []), "H6f": {"hidden_files_opened": leaks, "pass": leaks == 0}}


if __name__ == "__main__":
    out = {"grid_table": table(), **h1_h3(), "vote": h4() if vote else {}, "tuning": h6()}
    json.dump(out, open(os.path.join(D, "results_verdicts.json"), "w"), indent=1)
    for k, v in out.items():
        if isinstance(v, dict) and "pass" in v: print(k, "PASS" if v["pass"] else "FAIL")
        elif isinstance(v, dict) and "a_pass" in v: print(k, "a", v["a_pass"], "b", v["b_pass"])
    for k in ("H4a", "H4b", "H4c", "H4d"):
        if k in out["vote"]: print(k, "PASS" if out["vote"][k]["pass"] else "FAIL")
    for k in ("H6a", "H6b", "H6c", "H6f"):
        if k in out["tuning"]: print(k, "PASS" if out["tuning"][k]["pass"] else "FAIL", {kk: vv for kk, vv in out["tuning"][k].items() if kk != "pass"})
