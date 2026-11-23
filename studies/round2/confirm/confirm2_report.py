"""Round 2 verdicts from results/*.json, applied mechanically as PREREGISTRATION.md section 4 states. Writes ../RESULTS.md.

  python3 confirm2_report.py [--gate TEXT] [--tests TEXT]
"""
import json, os, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.join(HERE, "results")
CONTROL = "control_degree"


def load(name):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else []


def group(recs):
    g = {}
    for r in recs:
        g.setdefault(r["world"], []).append(r)
    return g


def stat(rs, prof, key):
    xs = [r["profiles"][prof].get(key) for r in rs if prof in r["profiles"]]
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"mean": statistics.mean(xs), "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0, "n": len(xs)}


def tol(s, floor=0.01):
    return max(2 * (s["sd"] if s else 0), floor)


def nonharm(G, worlds, p, q, keys=("precision", "recall")):
    """p vs comparison q, no-harm on precision (skipped if p abstains) and recall. Returns list of failures."""
    fails = []
    for w in worlds:
        for k in keys:
            sp, sq = stat(G[w], p, k), stat(G[w], q, k)
            if sq is None:
                continue
            if sp is None:
                if k == "precision":
                    continue           # p abstains: no precision harm
                fails.append(f"{w}: {p} {k} undef. vs {sq['mean']:.3f}"); continue
            if sp["mean"] < sq["mean"] - tol(sq):
                fails.append(f"{w}: {p} {k} {sp['mean']:.3f} < {q} {sq['mean']:.3f} - {tol(sq):.3f}")
    return fails


def fmt(s, d=3):
    return "undef." if s is None else (f"{s['mean']:.{d}f}" if s["sd"] == 0 else f"{s['mean']:.{d}f} ± {s['sd']:.{d}f}")


def main():
    sealed, real = load("sealed.json"), load("real.json")
    GS, GR = group(sealed), group(real)
    G = {**GS, **GR}
    structs = [w for w in GS if w != CONTROL]; reals = list(GR)
    allw = structs + reals
    V = {}
    # H1
    f = []
    for q, p in (("egm-default", "r2-default"), ("egm-ts0", "r2-ts0"), ("policy-strict", "r2-strict"), ("policy-tendency", "r2-tendency")):
        f += nonharm(G, allw, p, q)
    V["H1"] = (not f, f)
    # H2
    better, worse = [], []
    for p, q in (("r2-default", "egm-default"), ("r2-strict", "policy-strict"), ("r2-tendency", "policy-tendency"), ("r2-tendency-stab90", "policy-tendency")):
        for w in structs:
            sp, sq = stat(G[w], p, "aurc"), stat(G[w], q, "aurc")
            if sp is None or sq is None:
                continue
            t = max(2 * max(sp["sd"], sq["sd"]), 0.005)
            if sp["mean"] < sq["mean"] - t:
                better.append(f"{w}: {p} {sp['mean']:.4f} < {q} {sq['mean']:.4f} - {t:.4f}")
            if sp["mean"] > sq["mean"] + t:
                worse.append(f"{w}: {p} {sp['mean']:.4f} > {q} {sq['mean']:.4f} + {t:.4f}")
    V["H2"] = (bool(better) and not worse, ["improvements: " + ("; ".join(better) or "none")] + worse)
    # H3
    f, answers = [], 0
    for w in allw:
        s = stat(G[w], "r2-strict", "precision")
        if s is not None:
            if w in structs:
                answers += 1
            if s["mean"] < 0.95:
                f.append(f"{w}: r2-strict precision {s['mean']:.3f} < 0.95")
    if answers < 7:
        f.append(f"r2-strict answers on {answers} of {len(structs)} structures (< 7)")
    f += [x for x in nonharm(G, structs, "r2-strict", "r2-ts0", keys=("recall",))]
    V["H3"] = (not f, f)
    # H4
    f, up = [], []
    for w in allw:
        sp, sq = stat(G[w], "r2-tendency-stab90", "precision"), stat(G[w], "r2-tendency", "precision")
        if sp is None or sq is None:
            continue
        if sp["mean"] < sq["mean"] - 0.005:
            f.append(f"{w}: stab90 {sp['mean']:.3f} < tendency {sq['mean']:.3f} - 0.005")
        if sp["mean"] > sq["mean"] + 0.005:
            up.append(w)
    if len(up) < 3:
        f.append(f"higher by > 0.005 on {len(up)} ({', '.join(up) or 'none'}), need 3")
    V["H4"] = (not f, f + [f"higher on: {', '.join(up)}"])

    def rare(p):
        out = []
        if "conditional_rare" not in G:
            return ["conditional_rare missing"]
        sp, sr = stat(G["conditional_rare"], p, "precision"), stat(G["conditional_rare"], p, "recall")
        if sp is None or sp["mean"] < 0.95:
            out.append(f"conditional_rare: {p} precision {fmt(sp)} < 0.95")
        if sr is None or sr["mean"] < 0.8:
            out.append(f"conditional_rare: {p} recall {fmt(sr)} < 0.8")
        return out
    V["H5"] = (not (x := rare("cond-holdout") + nonharm(G, allw, "cond-holdout", "cond-shipped")), x)
    V["H6"] = (not (x := rare("cond-r1") + nonharm(G, [w for w in allw if w != "conditional_rare"], "cond-r1", "egm-default")), x)
    # H7
    f = [f"{r['world']} {r['seed']}: {r['nesting']['r2-strict<=r2-tendency']}" for r in sealed + real if r["nesting"].get("r2-strict<=r2-tendency")]
    V["H7"] = (not f, f)
    # H8
    f = []
    egm_profiles = [p for p in (sealed or real)[0]["profiles"] if not p.startswith("B")]
    for r in GS.get(CONTROL, []):
        for p in egm_profiles:
            if r["profiles"][p]["new"]:
                f.append(f"control_degree {r['seed']}: {p} new {r['profiles'][p]['new']}")
    for r in sealed + real:
        for p in egm_profiles:
            if r["profiles"][p].get("invented_unseen"):
                f.append(f"{r['world']} {r['seed']}: {p} invented {r['profiles'][p]['invented_unseen']}")
    V["H8"] = (not f, f)
    # H9
    f = []
    for r in sealed + real:
        for p in egm_profiles:
            if r["profiles"][p].get("proofs_invalid"):
                f.append(f"{r['world']} {r['seed']}: {p} proofs_invalid {r['profiles'][p]['proofs_invalid']}")
        for p, s in r["counterfactual"].items():
            if s.get("FAIL"):
                f.append(f"{r['world']} {r['seed']}: {p} counterfactual FAIL {s['FAIL']}")
    cf = sum(s.get("checked", 0) for r in sealed for s in r["counterfactual"].values())
    V["H9"] = (not f, f + [f"{cf} counterfactual tests"])
    gate = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--gate=")), "not run")
    tests = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--tests=")), "not run")
    V["K-H0"] = ("221/221" in gate and "OK" in tests, [f"gate: {gate}", f"tests: {tests}"])

    L = ["# Round 2: confirmation results\n",
         "Generated by `confirm/confirm2_report.py` from `confirm/results/sealed.json` and `confirm/results/real.json`; "
         "do not edit by hand. Criteria: `PREREGISTRATION.md` (hash in `prereg_hash.txt`). Deviations: `DEVIATIONS.md`. "
         "Reading and decisions: `CONFIRMATION.md`.\n",
         f"{len(sealed)} sealed runs ({len(GS)} structures), {len(real)} real-data runs ({len(GR)} sets).\n",
         "## Verdicts\n", "| ID | Verdict | Detail |", "|---|---|---|"]
    for k, (ok, det) in V.items():
        d = "<br>".join(det[:12]) + (f"<br>… {len(det) - 12} more" if len(det) > 12 else "")
        L.append(f"| {k} | {'pass' if ok else '**FAIL**'} | {d} |")
    L.append("")
    profs = egm_profiles
    for title, Gx in (("Sealed structures", GS), ("Real data", GR)):
        L.append(f"## {title}: precision / recall / new / AURC (mean ± sd over seeds)\n")
        for w, rs in Gx.items():
            L.append(f"### {w}\n"); L.append("| profile | precision | recall | new | AURC |"); L.append("|---|---|---|---|---|")
            for p in list(rs[0]["profiles"]):
                L.append(f"| {p} | {fmt(stat(rs, p, 'precision'))} | {fmt(stat(rs, p, 'recall'))} | {fmt(stat(rs, p, 'new'), 0)} | {fmt(stat(rs, p, 'aurc'), 4)} |")
            conds = {}
            for r in rs:
                for p, cl in r.get("conditions_learned", {}).items():
                    for c in cl:
                        conds.setdefault(p, {}).setdefault(c, 0); conds[p][c] += 1
            if conds:
                L.append("\nConditions learned (rule: seeds):\n")
                for p, cs in conds.items():
                    L.append(f"- {p}: " + "; ".join(f"`{c}`: {n}" for c, n in sorted(cs.items())))
            L.append("")
    open(os.path.join(HERE, "..", "RESULTS.md"), "w").write("\n".join(L) + "\n")
    for k, (ok, det) in V.items():
        print(k, "pass" if ok else "FAIL", det[:4])


if __name__ == "__main__":
    main()
