"""Round 1 confirmation, exactly as pre-registered (PREREGISTRATION.md section 6; interpretations in DEVIATIONS.md D2).

  python3 confirm.py sealed      sealed worlds (studies/sealed, every structure, seeds 1000-1004)
  python3 confirm.py real        real-data sets (REALDATA.md, splits 1000-1004)
  python3 confirm.py report      verdicts and tables -> ../RESULTS.md (from results/*.json, gate and bench files)

Run once. Nothing here is tuned; the built-in policies and the criteria are frozen.
"""
import json, os, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(STUDY, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "capability", "tools")); sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "studies", "sealed")); sys.path.insert(0, HERE)
import egm  # noqa: E402
from interface import EGMAdapter, parse_fact  # noqa: E402
import baselines, counterfactual, cworlds, metrics  # noqa: E402

RES = os.path.join(HERE, "results")
SEEDS = list(range(1000, 1005))
EGM = ["egm-default", "egm-ts0", "policy-strict", "policy-tendency"]
KEYS = ["precision", "recall", "new", "wrong", "correct", "aurc", "invented_unseen", "abstention", "undet_answered",
        "proof_validity", "proofs_invalid", "proofs_checked", "seconds", "peak_mb", "missing"]


def adapter(name, extra=None):
    st = dict(extra or {})
    if name == "egm-default":
        return EGMAdapter(st)
    if name == "egm-ts0":
        return EGMAdapter({**st, "TENDENCYSTEPS": 0})
    return EGMAdapter(st, policy=name.split("-", 1)[1])


def sealed_world(structure, seed):
    import gen_sealed
    lines, key = gen_sealed.world(structure, seed)
    rels = sorted(key["relations"], key=len, reverse=True)
    w = cworlds.World(structure, structure, seed, lines, rels, {tuple(x) for x in key["truth"]}, set(key.get("unseen", [])),
                      {(c[0], c[1], c[2]) for c in key.get("corrupted", [])},
                      {tuple(x) for x in key.get("undeterminable", [])}, {})
    w.recall_truth = {tuple(x) for x in key.get("hidden", [])}
    return w


def rule_precision(world, run, ev):
    """D-H1: per rule with >= 5 new facts under tendency: (agreement, rel, precision)."""
    S = cworlds.stated(world); by = {}
    for a in run.answers:
        if a.status == "derived" and a.fact not in S and a.rule:
            by.setdefault(a.rule, []).append(a.fact in world.truth)
    vec = {v["rule"]: v for v in ev}
    return [(vec[r]["agree"], vec[r]["rel"], sum(x) / len(x)) for r, x in by.items() if len(x) >= 5 and r in vec and vec[r]["agree"] is not None]


def evidence(lines, settings, policy):
    with egm.Engine(settings=settings) as e:
        e.ingest_many(lines); e.apply_policy(policy)
        return e.evidence()


def run_world(w, extra, counterfactual_n):
    rec = {"world": w.name, "seed": w.seed, "profiles": {}, "nesting": None, "counterfactual": {}, "d_h1": []}
    sets = {}
    for p in EGM:
        a = adapter(p, extra); r = a.run(w.lines, w.rels, [])
        rec["profiles"][p] = metrics.measure(w, r); sets[p] = {x.fact for x in r.answers}
        if p in ("policy-strict", "policy-tendency") and counterfactual_n:
            rec["counterfactual"][p] = counterfactual.summarize(counterfactual.check(a, w.lines, w.rels, r, n=counterfactual_n, seed=w.seed))
        if p == "policy-tendency":
            rec["d_h1"] = rule_precision(w, r, evidence(w.lines, extra or {}, "tendency"))
        if w.name == "dpkg":
            from realdata import dpkg_transitive
            S = cworlds.stated(w); rec.setdefault("dpkg_transitive", {})[p] = dpkg_transitive(w, sets[p] - S)
    rec["nesting"] = len(sets["policy-strict"] - sets["policy-tendency"])
    if not extra:   # trivial and external baselines on the sealed worlds (reported, no criterion)
        for b in baselines.BASELINES:
            rec["profiles"][b.name] = metrics.measure(w, b.run(w.lines, w.rels, []))
    return rec


def sealed():
    import gen_sealed
    structures = sorted(gen_sealed.STRUCTURES) if hasattr(gen_sealed, "STRUCTURES") else None
    if structures is None:
        structures = ["inverse", "symmetric", "transitive", "composition", "path3", "conditional", "conditional_control",
                      "conditional_decoy", "branching", "depth", "noise", "control", "hub", "ambiguous"]
    out = []
    for st in structures:
        for seed in SEEDS:
            t = time.time(); out.append(run_world(sealed_world(st, seed), None, 20))
            print(st, seed, f"{time.time() - t:.1f}s", flush=True)
            json.dump(out, open(os.path.join(RES, "sealed.json"), "w"))
    return out


def real():
    import realdata
    out = []
    for name in realdata.SETS:
        for seed in SEEDS:
            w = realdata.load(name, seed); t = time.time()
            out.append(run_world(w, {"MAXWORDS": w.maxwords}, 0))
            print(name, seed, f"{time.time() - t:.1f}s", flush=True)
            json.dump(out, open(os.path.join(RES, "real.json"), "w"))
    return out


if __name__ == "__main__":
    os.makedirs(RES, exist_ok=True)
    cmd = sys.argv[1]
    if cmd == "sealed":
        sealed()
    elif cmd == "real":
        real()
    elif cmd == "report":
        import confirm_report
        confirm_report.main()
