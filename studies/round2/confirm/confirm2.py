"""Round 2 confirmation (PREREGISTRATION.md). Run only after the pre-registration hash.

  python3 confirm2.py sealed     Round 2 sealed worlds (studies/sealed2), every structure, seeds 2000-2004
  python3 confirm2.py real       realdata2 sets, splits 2000-2004
  python3 confirm2.py dry        the same code on development data only (Round 1 sealed conditional, seed 1000;
                                 hidden-cov50 seed 0): harness check, not evidence
Results: results/sealed.json, results/real.json. Verdicts: confirm2_report.py.
"""
import copy, dataclasses, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies", "capability", "tools"), os.path.join(ROOT, "studies", "sealed2"), HERE]
import egm  # noqa: E402
from egm.policy import BUILTINS  # noqa: E402
from interface import EGMAdapter  # noqa: E402
import baselines, counterfactual, cworlds, metrics  # noqa: E402

RES = os.path.join(HERE, "results")
SEEDS = list(range(2000, 2005))
STRUCTURES = ["reversed_weak", "graded", "skewed", "multivalue", "exceptions", "competing", "sparse",
              "conditional_rare", "chain_noise", "control_degree"]


def stab_policy():
    """tendency with minStability 0.9 in both strata (the W2 profile)."""
    p = BUILTINS["tendency"]; ext = copy.deepcopy(p.extension); ext["thresholds"] = dict(ext["thresholds"], minStability=0.9)
    return dataclasses.replace(p, name="tendency-stab90", version="r2", builtin=False,
                               thresholds=dict(p.thresholds, minStability=0.9), extension=ext)


C1 = {"COVSOURCE": 1}
# name -> (settings, policy); Round 1 frozen profiles first (the comparison), then Round 2 candidates
PROFILES = {
    "egm-default": ({}, None), "egm-ts0": ({"TENDENCYSTEPS": 0}, None),
    "policy-strict": ({}, "strict"), "policy-tendency": ({}, "tendency"),
    "r2-default": (C1, None), "r2-ts0": ({**C1, "TENDENCYSTEPS": 0}, None),
    "r2-strict": (C1, "strict"), "r2-tendency": (C1, "tendency"), "r2-tendency-stab90": (C1, "stab"),
    "cond-r1": ({"CONDITIONS": 1}, None),
    "cond-shipped": ({**C1, "CONDITIONS": 1}, None), "cond-holdout": ({**C1, "CONDITIONS": 1, "CONDHOLDOUT": 1}, None),
}
COUNTERFACTUAL = ("r2-strict", "r2-tendency")
NESTING = (("r2-strict", "r2-tendency"), ("policy-strict", "policy-tendency"), ("r2-tendency-stab90", "r2-tendency"))


def adapter(name, extra=None):
    st, pol = PROFILES[name]
    return EGMAdapter({**(extra or {}), **st}, policy=stab_policy() if pol == "stab" else pol)


def sealed_world(structure, seed):
    import gen_sealed2
    lines, key = gen_sealed2.world(structure, seed)
    rels = sorted(key["relations"], key=len, reverse=True)
    w = cworlds.World(structure, structure, seed, lines, rels, {tuple(x) for x in key["truth"]}, set(key.get("unseen", [])),
                      {(c[0], c[1], c[2]) for c in key.get("corrupted", [])},
                      {tuple(x) for x in key.get("undeterminable", [])}, {})
    w.recall_truth = {tuple(x) for x in key.get("hidden", [])}
    w.conditions = key.get("conditions") or []
    return w


def run_world(w, extra, counterfactual_n, with_baselines):
    rec = {"world": w.name, "seed": w.seed, "profiles": {}, "nesting": {}, "counterfactual": {}, "conditions_learned": {}}
    sets = {}
    for p in PROFILES:
        a = adapter(p, extra); t = time.time(); r = a.run(w.lines, w.rels, [])
        rec["profiles"][p] = metrics.measure(w, r); rec["profiles"][p]["wall"] = round(time.time() - t, 2)
        sets[p] = {x.fact for x in r.answers}
        if p in COUNTERFACTUAL and counterfactual_n:
            rec["counterfactual"][p] = counterfactual.summarize(counterfactual.check(a, w.lines, w.rels, r, n=counterfactual_n, seed=w.seed))
        if p.startswith("cond-"):
            st, _ = PROFILES[p]
            with egm.Engine(settings={**(extra or {}), **st}) as e:
                e.ingest_many(w.lines)
                rec["conditions_learned"][p] = sorted(v["rule"] for v in e.evidence() if " if " in v["rule"])
    for s, t in NESTING:
        rec["nesting"][f"{s}<={t}"] = len(sets[s] - sets[t])
    if with_baselines:
        for b in baselines.BASELINES:
            rec["profiles"][b.name] = metrics.measure(w, b.run(w.lines, w.rels, []))
    return rec


def sealed(structures=STRUCTURES, seeds=SEEDS, out_name="sealed.json"):
    out = []
    for st in structures:
        for seed in seeds:
            t = time.time(); out.append(run_world(sealed_world(st, seed), None, 20, True))
            print(st, seed, f"{time.time() - t:.1f}s", flush=True)
            json.dump(out, open(os.path.join(RES, out_name), "w"))
    return out


def real(out_name="real.json"):
    import realdata2
    out = []
    for name in realdata2.SETS:
        for seed in realdata2.SEEDS:
            w = realdata2.load(name, seed); t = time.time()
            out.append(run_world(w, {"MAXWORDS": w.maxwords}, 0, False))
            print(name, seed, f"{time.time() - t:.1f}s", flush=True)
            json.dump(out, open(os.path.join(RES, out_name), "w"))
    return out


def dry():
    sys.path.insert(0, os.path.join(ROOT, "studies", "sealed")); sys.path.insert(0, os.path.join(ROOT, "studies", "evidence_policy", "confirm"))
    import confirm
    recs = [run_world(confirm.sealed_world("conditional", 1000), None, 5, True), run_world(cworlds.load("hidden-cov50", 0), None, 0, False)]
    json.dump(recs, open(os.path.join(HERE, "dry_run.json"), "w"), indent=1, default=list)
    for r in recs:
        print(r["world"], {p: (m.get("precision"), m.get("recall"), m.get("new")) for p, m in r["profiles"].items()})
        print("  nesting", r["nesting"], "cf", r["counterfactual"], "conds", {k: len(v) for k, v in r["conditions_learned"].items()})


if __name__ == "__main__":
    os.makedirs(RES, exist_ok=True)
    {"sealed": sealed, "real": real, "dry": dry}[sys.argv[1]]()
