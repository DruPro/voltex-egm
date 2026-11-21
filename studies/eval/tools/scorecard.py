"""Capability scorecard: a baseline of the engine's general mechanisms, with variance across seeds and tier calibration.

  python3 scorecard.py [--seeds N] [--only SUBSTR] [--out FILE]     default: 5 seeds, ../baseline/scorecard.json

Nothing here is new world logic. Worlds come from the existing generators (studies/noise/hidden/gen.py via
studies/noise/tools/lib.py, and tests/worlds.py); scoring is lib.score (precision and recall against complete truth,
facts invented about unseen names, corrupted facts flagged). Added on top, because the audit found them unmeasured:
  - calibration: precision of law-tier and of tendency-tier new facts, separately (the engine claims law = estimated
    reliability >= LAW, 0.95 by default);
  - variance: every cell over several seeds, reported as mean, sd, min, max;
  - a control world with no structure (random links), where the right answer is to derive nothing.
Each cell names the capability it measures and the layer that owns it (docs/EVALUATION.md).
The engine binary comes from VOLTEX (default build/voltex2), as in studies/noise.
"""
import json, os, random, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "tools")); sys.path.insert(0, os.path.join(ROOT, "tests"))
import lib     # noqa: E402  (world generation cache, engine run, scoring)
import worlds  # noqa: E402
OBS = os.path.join(STUDY, "obs")


def tests_world(name, seed):
    """tests/worlds.py worlds in lib.score's truth format (truth = every true fact, stated or not)."""
    if name == "harvest":
        lines, _wrong = worlds.harvest(seed=seed)
        rels = ["produces", "lives in", "works as", "harvests"]
        truth = {tuple([r] + l.split(f" {r} ", 1)) for l in lines for r in rels if f" {r} " in l}   # stated, all true
        goods, town, job = {}, {}, {}
        for r, a, b in truth:
            if r == "produces": goods.setdefault(a, []).append(b)
            if r == "lives in": town[a] = b
            if r == "works as": job[a] = b
        for p, j in job.items():   # the generator's rule: only farmers and miners harvest what their town produces
            if j in ("farmer", "miner"):
                truth |= {("harvests", p, g) for g in goods.get(town[p], [])}
        return lines, {"relations": rels, "truth": sorted(map(list, truth)), "corrupted": []}
    if name == "remainders":
        lines, hidden = worlds.remainders(seed=seed)
        rels = ["is three more than", "is one more than", "has remainder"]
        truth = {tuple([r] + l.split(f" {r} ", 1)) for l in lines for r in rels if f" {r} " in l}
        truth |= {("has remainder", n, v) for n, v in hidden.items()}
        return lines, {"relations": rels, "truth": sorted(map(list, truth)), "corrupted": []}
    if name == "random_links":   # control: no rule holds, so every derived fact is a false discovery
        r = random.Random(seed); names = [f"e{i}" for i in range(300)]
        rels = ["is linked to", "is near", "knows"]
        truth = {(rr, a, b) for rr in rels for _ in range(600) for a, b in [r.sample(names, 2)]}
        lines = [f"{a} {rr} {b}" for rr, a, b in sorted(truth)]
        return lines, {"relations": rels, "truth": sorted(map(list, truth)), "corrupted": []}
    raise KeyError(name)


def obs_for(src, name, seed, kw):
    if src == "noise":
        p, h = lib.world(name, seed=seed, **kw); return p, h
    lines, h = tests_world(name, seed)
    os.makedirs(OBS, exist_ok=True); p = os.path.join(OBS, f"{name}_s{seed}.txt")
    open(p, "w").write("\n".join(lines) + "\n"); return p, h


# capability, owning layer, world source, world, generator args, settings, what a good result is
CELLS = [
    ("induction: sample size", "induction", "noise", "company", {"scale": 1}, {}, "high P and R"),
    ("induction: sample size", "induction", "noise", "company", {"scale": 4}, {}, "R does not fall with scale"),
    ("induction: sparsity", "induction", "noise", "hidden", {"scale": 1, "coverage": 0.3}, {}, "P stays high as coverage falls"),
    ("induction: sparsity", "induction", "noise", "hidden", {"scale": 1, "coverage": 0.5}, {}, ""),
    ("induction: sparsity", "induction", "noise", "hidden", {"scale": 1, "coverage": 0.7}, {}, ""),
    ("evidence: noise", "evidence", "noise", "company", {"scale": 1, "noise": 0.15}, {}, "wrong facts flagged"),
    ("evidence: noise", "evidence", "noise", "company", {"scale": 1, "noise": 0.30}, {}, ""),
    ("evidence: repeated reports", "evidence", "noise", "company", {"scale": 1, "noise": 0.15, "reports": 3}, {"VOTE": 1}, "VOTE outvotes wrong reports"),
    ("expressiveness: branching (trees)", "induction", "noise", "gates", {"per_kind": 200}, {}, "nothing without TREES"),
    ("expressiveness: branching (trees)", "induction", "noise", "gates", {"per_kind": 200}, {"TREES": 1}, "outputs computed"),
    ("expressiveness: multi-premise", "induction", "noise", "lineage", {}, {}, "nothing at CHAIN 2"),
    ("expressiveness: multi-premise", "induction", "noise", "lineage", {}, {"CHAIN": 3}, "great-grandparents"),
    ("expressiveness: conditional", "induction", "tests", "harvest", {}, {}, "errors for non-harvesters"),
    ("expressiveness: conditional", "induction", "tests", "harvest", {}, {"CONDITIONS": 1}, "errors cut"),
    ("inference: depth", "inference", "tests", "remainders", {}, {}, "cap binds on long chains"),
    ("inference: depth", "inference", "tests", "remainders", {}, {"DEPTH": 0}, "more recovered, 0 wrong"),
    ("control: no structure", "induction", "tests", "random_links", {}, {}, "derive nothing"),
]


def tiers(out, h, obs_path):
    """New facts by tier, and how many are true (calibration)."""
    rels = sorted(h["relations"], key=len, reverse=True); T = {tuple(x) for x in h["truth"]}
    stated = lib.facts_of(open(obs_path).read().splitlines(), rels)
    c = {"law": [0, 0], "tendency": [0, 0]}
    for l in out.splitlines():
        if l.startswith("FACT\t"):
            p = l.split("\t"); f = lib.parse_fact(p[1], rels)
            if f and f not in stated and len(p) > 2 and p[2] in c:
                c[p[2]][0] += 1; c[p[2]][1] += f in T
    return {f"{k}_new": v[0] for k, v in c.items()} | {f"{k}_precision": (v[1] / v[0] if v[0] else None) for k, v in c.items()}


def summary(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return None
    return {"mean": round(statistics.mean(xs), 4), "sd": round(statistics.stdev(xs), 4) if len(xs) > 1 else 0.0,
            "min": round(min(xs), 4), "max": round(max(xs), 4), "n": len(xs)}


def main():
    a = sys.argv[1:]
    seeds = int(a[a.index("--seeds") + 1]) if "--seeds" in a else 5
    only = a[a.index("--only") + 1] if "--only" in a else ""
    out_path = a[a.index("--out") + 1] if "--out" in a else os.path.join(STUDY, "baseline", "scorecard.json")
    res = []
    for cap, layer, src, name, kw, st, good in CELLS:
        cid = f"{name}|{','.join(f'{k}={v}' for k, v in kw.items())}|{','.join(f'{k}={v}' for k, v in st.items()) or 'default'}"
        if only and only not in cid: continue
        per = []
        for s in range(seeds):
            p, h = obs_for(src, name, s, kw)
            t = time.time(); out = lib.run(p, lib.settings_lines(st)); dt = time.time() - t
            r = lib.score(out, p, h); r.update(tiers(out, h, p)); r["seconds"] = round(dt, 2); r["seed"] = s
            # lib.score returns 1.0 for a rate with nothing to divide by; report it as undefined, with the counts
            rels = sorted(h["relations"], key=len, reverse=True)
            missing = {tuple(x) for x in h["truth"]} - lib.facts_of(open(p).read().splitlines(), rels)
            r["missing"] = len(missing)
            if r["derived_new"] == 0: r["precision"] = None
            if not missing: r["recall"] = None
            per.append(r)
        keys = ["precision", "recall", "derived_new", "missing", "wrong", "invented_unseen", "flagged", "flag_hits",
                "law_new", "law_precision", "tendency_new", "tendency_precision", "seconds"]
        row = {"cell": cid, "capability": cap, "layer": layer, "expect": good, "seeds": seeds,
               "summary": {k: summary([r.get(k) for r in per]) for k in keys}, "per_seed": per}
        res.append(row)
        S = row["summary"]; f = lambda k: "-" if S[k] is None else f"{S[k]['mean']:.3f}±{S[k]['sd']:.3f}"
        print(f"{cid:58s} P {f('precision')} R {f('recall')} law-P {f('law_precision')} tend-P {f('tendency_precision')} "
              f"new {S['derived_new']['mean']:.0f} {S['seconds']['mean']:.1f}s", flush=True)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    binary = os.environ.get("VOLTEX", os.path.join(ROOT, "build", "voltex2"))
    import hashlib
    meta = {"binary_sha256": hashlib.sha256(open(binary, "rb").read()).hexdigest(),
            "tool_commit": os.popen(f"git -C {ROOT} rev-parse --short HEAD").read().strip(), "seeds": seeds}
    json.dump({"meta": meta, "cells": res}, open(out_path, "w"), indent=1)
    print("wrote", os.path.relpath(out_path, ROOT))   # repo-relative: logs are committed


if __name__ == "__main__":
    main()
