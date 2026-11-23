"""Verdicts for Round 1 confirmation, computed exactly as PREREGISTRATION.md section 6 states, with the interpretations
fixed in DEVIATIONS.md D2 before the run. Writes ../RESULTS.md from results/*.json (+ gate.txt, stress.txt, tests.txt).
Written before the confirmation run; any later change to this file is a deviation."""
import json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.dirname(HERE); RES = os.path.join(HERE, "results")
COUNT_MIN = 20   # derived facts per seed for a world to count towards precision criteria
POL = ("policy-strict", "policy-tendency")


def S(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"mean": statistics.mean(xs), "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0, "min": min(xs), "max": max(xs), "n": len(xs)}


def group(recs):
    g = {}
    for r in recs:
        g.setdefault(r["world"], []).append(r)
    return g


def summarize(recs):
    out = {}
    for w, rs in group(recs).items():
        profs = rs[0]["profiles"].keys()
        out[w] = {"seeds": [r["seed"] for r in rs],
                  "profiles": {p: {k: S([r["profiles"][p].get(k) for r in rs]) for k in rs[0]["profiles"][p]} for p in profs},
                  "nesting": [r["nesting"] for r in rs],
                  "counterfactual": {p: {k: sum(r["counterfactual"].get(p, {}).get(k, 0) or 0 for r in rs) for k in ("removed", "alternative", "FAIL", "checked")}
                                     for p in POL},
                  "d_h1": [x for r in rs for x in r["d_h1"]],
                  "dpkg_transitive": [r.get("dpkg_transitive") for r in rs if r.get("dpkg_transitive")]}
    return out


def mean(x):
    return None if x is None else x["mean"]


def spearman(xs, ys):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    if len(xs) < 3:
        return None
    a, b = rank(xs), rank(ys); ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b)); den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else None


def verdicts(W):
    """W: world -> summary, sealed and real together. Returns rows (id, pass, detail) and per-hypothesis notes."""
    rows = []
    # C-H1
    with_facts = [w for w, s in W.items() if mean(s["profiles"]["egm-default"]["new"]) and s["profiles"]["egm-default"]["aurc"] and s["profiles"]["policy-tendency"]["aurc"]]
    improve, strict_improve, worse = [], [], []
    for w in with_facts:
        d = W[w]["profiles"]["egm-default"]["aurc"]; t = W[w]["profiles"]["policy-tendency"]["aurc"]
        if t["mean"] <= d["mean"] - 2 * d["sd"]:
            improve.append(w)
        if t["mean"] < d["mean"] - 2 * d["sd"] - 1e-12:
            strict_improve.append(w)
        if t["mean"] > d["mean"] + 2 * d["sd"] + 1e-12:
            worse.append(w)
    ok = len(improve) * 2 >= len(with_facts) and not worse
    rows.append(("C-H1", ok, f"improved (<= default - 2 sd) on {len(improve)} of {len(with_facts)} worlds with derived facts "
                 f"(strictly lower: {len(strict_improve)}); worse than default + 2 sd on: {', '.join(worse) or 'none'}"))
    # C-H2
    prec_fail, rec_fail, counted = [], [], []
    for w, s in W.items():
        st = s["profiles"]["policy-strict"]; ts = s["profiles"]["egm-ts0"]
        if mean(st["new"]) is not None and st["new"]["mean"] >= COUNT_MIN:
            counted.append(w)
            if st["precision"] is None or st["precision"]["mean"] < 0.95:
                prec_fail.append(f"{w} ({fmt(st['precision'])})")
        if st["recall"] is not None and ts["recall"] is not None and st["recall"]["mean"] < ts["recall"]["mean"] - 2 * ts["recall"]["sd"] - 1e-12:
            rec_fail.append(f"{w} ({st['recall']['mean']:.3f} vs {ts['recall']['mean']:.3f} ± {ts['recall']['sd']:.3f})")
    rows.append(("C-H2", not prec_fail and not rec_fail,
                 f"precision >= 0.95 on {len(counted) - len(prec_fail)} of {len(counted)} counted worlds (fails: {', '.join(prec_fail) or 'none'}); "
                 f"recall below TENDENCYSTEPS 0 - 2 sd on: {', '.join(rec_fail) or 'none'}"))
    # C-H3
    viol = {w: max(s["nesting"]) for w, s in W.items() if max(s["nesting"]) > 0}
    rows.append(("C-H3", not viol, f"answers of strict outside tendency: {'0 everywhere' if not viol else viol}"))
    # C-H4
    inv = {f"{w}/{p}": s["profiles"][p]["invented_unseen"]["max"] for w, s in W.items() for p in POL
           if s["profiles"][p]["invented_unseen"] and s["profiles"][p]["invented_unseen"]["max"] > 0}
    ctrl = {p: W["control"]["profiles"][p]["new"]["max"] for p in POL} if "control" in W else {}
    ok = not inv and all(v == 0 for v in ctrl.values()) and bool(ctrl)
    rows.append(("C-H4", ok, f"invented facts: {inv or 'none'}; derived on the control world (max per seed): {ctrl or 'control missing'}"))
    # C-H5
    invalid = {f"{w}/{p}": s["profiles"][p]["proofs_invalid"]["max"] for w, s in W.items() for p in POL
               if s["profiles"][p]["proofs_invalid"] and s["profiles"][p]["proofs_invalid"]["max"] > 0}
    checked = sum(int(s["profiles"][p]["proofs_checked"]["mean"] * s["profiles"][p]["proofs_checked"]["n"]) for s in W.values() for p in POL if s["profiles"][p]["proofs_checked"])
    cf = {p: {k: sum(s["counterfactual"][p][k] for s in W.values()) for k in ("removed", "alternative", "FAIL", "checked")} for p in POL}
    ok = not invalid and all(cf[p]["FAIL"] == 0 for p in POL)
    rows.append(("C-H5", ok, f"proof validity: {checked} proofs checked, invalid: {invalid or 'none'}; counterfactual (sealed): "
                 + "; ".join(f"{p}: {c['checked']} checked, {c['removed']} removed, {c['alternative']} alternative, {c['FAIL']} FAIL" for p, c in cf.items())))
    return rows


def fmt(x, d=3):
    if x is None:
        return "undef."
    return f"{x['mean']:.{d}f}" if x["sd"] == 0 else f"{x['mean']:.{d}f} ± {x['sd']:.{d}f}"


def main():
    sealed = summarize(json.load(open(os.path.join(RES, "sealed.json"))))
    real = summarize(json.load(open(os.path.join(RES, "real.json"))))
    W = {**sealed, **real}
    L = ["# Round 1 confirmation: results", "",
         "Generated by `confirm/confirm_report.py` (written before the run) from `confirm/results/`; do not edit by hand. "
         "Pre-registration `PREREGISTRATION.md` (sha256 in `prereg_hash.txt`), deviations `DEVIATIONS.md`. Sealed worlds: "
         "`studies/sealed`, seeds 1000-1004, run once. Real data: `confirm/REALDATA.md`, splits 1000-1004.", "",
         "## Verdicts", "", "| ID | Result | Detail |", "|---|---|---|"]
    for i, ok, d in verdicts(W):
        L.append(f"| {i} | {'pass' if ok else 'FAIL'} | {d} |")
    for name, fn in (("K-H0", "gate.txt"), ("K-H0 (stress bench)", "stress.txt"), ("X-H1", "tests.txt")):
        p = os.path.join(RES, fn)
        L.append(f"| {name} | {open(p).read().strip() if os.path.exists(p) else 'not run'} | |")
    d = [x for s in W.values() for x in s["d_h1"]]
    ra = spearman([x[0] for x in d], [x[2] for x in d]); rr = spearman([x[1] for x in d], [x[2] for x in d])
    L.append(f"| D-H1 (diagnostic) | reported | rules with >= 5 new facts under tendency: {len(d)}; Spearman with rule precision: "
             f"agreement {'undef.' if ra is None else f'{ra:.3f}'}, rel {'undef.' if rr is None else f'{rr:.3f}'} |")
    for title, block in (("Sealed worlds", sealed), ("Real data", real)):
        L += ["", f"## {title}", "", "| World | Profile | Precision | Recall | New | Wrong | AURC | Invented | Proofs invalid | Seconds |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for w, s in block.items():
            for p, m in s["profiles"].items():
                L.append(f"| {w} | {p} | {fmt(m['precision'])} | {fmt(m['recall'])} | {fmt(m['new'], 0)} | {fmt(m['wrong'], 0)} | "
                         f"{fmt(m['aurc'])} | {fmt(m['invented_unseen'], 0)} | {fmt(m['proofs_invalid'], 0)} | {fmt(m['seconds'], 2)} |")
    if real.get("dpkg", {}).get("dpkg_transitive"):
        L += ["", "Secondary view, no criterion (dpkg): derived `depends on` facts that lie in the transitive Depends closure, per split:", ""]
        for t in real["dpkg"]["dpkg_transitive"]:
            L.append("- " + "; ".join(f"{p}: {v['in_transitive_closure']} of {v['derived_depends']}" for p, v in t.items()))
    open(os.path.join(STUDY, "RESULTS.md"), "w").write("\n".join(L) + "\n")
    print("wrote RESULTS.md")


if __name__ == "__main__":
    main()
