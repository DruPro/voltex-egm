"""Verdicts and showcase proofs, recomputed from the results files.

  python3 report.py      writes ../results_summary.json (all rounds, verdicts) and ../showcase.json (proof trees)
"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
RUNS = ["default", "depth1", "depth2", "depth0", "chain3", "trees", "full"]
SUB, PKG = "is a subclass of", "belongs to package"


def load(rd): return {n: json.load(open(os.path.join(STUDY, rd, n + ".json"))) for n in RUNS}


def verdicts(R, bind):
    pr = lambda n, r: R[n]["per_relation"][r]
    v = {}
    rec = [pr(n, SUB)["recall"] for n in ("depth1", "depth2", "default", "depth0")]
    precs = [pr(n, SUB)["precision"] for n in ("depth1", "depth2", "default", "depth0")]
    v["P1"] = all(a <= b for a, b in zip(rec, rec[1:])) and all(p is not None and p >= 0.95 for p in precs)
    c = pr("chain3", PKG)
    v["P2"] = pr("default", PKG)["recall"] < 0.10 and c["recall"] >= 0.90 and (c["precision"] or 0) >= 0.95
    t = pr("trees", bind); v["P3"] = t["recall"] >= 0.95 and (t["precision"] or 0) >= 0.99
    v["P4"] = R["full"]["recall"] >= 0.90 and (R["full"]["precision"] or 0) >= 0.95
    v["P5"] = all(R[n]["wall_s"] < 900 and R[n]["peak_rss_mb"] < 4096 for n in RUNS)
    v["P6"] = pr("depth0", SUB)["recall"] - pr("depth1", SUB)["recall"] >= 0.10
    f = R["full"]["per_relation"]
    v["P7"] = all((f[r]["precision"] or 0) >= 0.99 for r in (SUB, PKG, bind)) and f["other"]["derived"] == 0
    v["P8"] = all(f[r]["recall"] >= 0.95 for r in (SUB, PKG, bind))
    return v


def main():
    out = {}
    for rd, bind, ps in (("results", "binds", 5), ("results_r2", "is bound to", 6), ("results_r3", "is bound to", 8)):
        R = load(rd); v = verdicts(R, bind)
        out[rd] = {"verdicts": {k: ("pass" if x else "fail") for k, x in list(v.items())[:ps]},
                   "runs": {n: {k: R[n][k] for k in ("settings", "derived_new", "correct", "wrong", "recovered", "hidden",
                                                      "precision", "recall", "wall_s", "infer_s", "peak_rss_mb", "rounds")}
                                | {"per_relation": R[n]["per_relation"]} for n in RUNS}}
    out["results_depth"] = {"exploratory": "ancestry of 70% of classes hidden (extract.py --r2 --hide-sub 0.7), round 3 settings",
                            "runs": {}}
    for n in ("d1", "d2", "d3", "d4", "d0"):
        x = json.load(open(os.path.join(STUDY, "results_depth", n + ".json")))
        out["results_depth"]["runs"][n] = {k: x[k] for k in ("settings", "wall_s", "rounds")} | \
            {"subclass": x["per_relation"][SUB], "proof_deepest": x["proofs"][SUB][0]}
    out["corpus"] = json.load(open(os.path.join(STUDY, "obs_r2", "stats.json")))
    json.dump(out, open(os.path.join(STUDY, "results_summary.json"), "w"), indent=1)
    for rd in out: print(rd, out[rd].get("verdicts", ""))
    showcase()


def showcase():
    """Proof trees from the round 3 `full` configuration, with the tier of every answer, and the longest chains."""
    import egm, run
    obs = os.path.join(STUDY, "obs_r2"); t = json.load(open(os.path.join(obs, "truth.json")))
    stated = {l.strip() for l in open(os.path.join(obs, "facts.txt"))}; truth = set(t["base"]) | set(t["targets"])
    key = {l.strip() for l in open(os.path.join(obs, "key.txt")) if l.strip()}
    inh = collections.defaultdict(set); rel = collections.defaultdict(dict)
    for f in t["base"]:
        s, _, rest = f.partition(" "); r, o = rest.rsplit(" ", 1); rel[r][s] = o
        if r == "inherits from": inh[s].add(o)
    def hops(a, b):   # shortest inheritance path length
        fr, d = {a}, 0
        while fr:
            d += 1; fr = {y for x in fr for y in inh[x]}
            if b in fr: return d
        return None
    st = {"MAXWORDS": 28500, "TENDENCYSTEPS": 0, "TREES": 1, "CHAIN": 3, "DEPTH": 0}
    with egm.open(os.path.join(obs, "facts.txt"), settings=st, binary=os.path.join(ROOT, "build", "voltex2")) as e:
        facts = e.infer_all()
        tiers = collections.Counter()
        new = []
        for f in facts:
            n = " ".join(f.fact.split())
            if n in stated: continue
            new.append((f, n)); tiers[f"{f.tier} {'correct' if n in truth else 'wrong'}"] += 1
        plain = lambda n: "____" not in n and not n.startswith("_")   # readable names first in the examples
        new.sort(key=lambda x: (not plain(x[1]), x[1]))
        subs = sorted(((hops(n.split()[0], n.split()[-1]) or 0, n) for f, n in new if SUB in n and n in key), reverse=True)
        deep = [run.proof(e, n) for _, n in subs[:3]]
        pkg = [run.proof(e, n) for f, n in new if PKG in n and n in key][:2]
        kinds = {}; tries = collections.Counter()
        for f, n in new:
            if "is bound to" not in n or n not in key: continue
            fn = n.split()[0][:-4]; k = (rel["has scope"][fn], rel["has decorator"][fn])
            if k in kinds or tries[k] >= 200: continue
            tries[k] += 1; p = run.proof(e, n)   # prefer a proof by the scope or decorator rule over a shortcut tree
            if "has scope" in str(p.get("rule")) or "has decorator" in str(p.get("rule")): kinds[k] = p
        wrong = [run.proof(e, n) for f, n in new if n not in truth][:2]
        miss = collections.Counter()
        got = {n for _, n in new}
        for m in key - got:
            fn = m.split()[0][:-4]; miss[f"{rel['has scope'].get(fn)} {rel['has decorator'].get(fn)}"] += 1
        rules = [r for r in e.rules()]
    sc = {"settings": st, "tiers": dict(tiers), "longest_hidden_subclass_hops": [h for h, _ in subs[:10]],
          "hops_histogram": dict(collections.Counter(h for h, _ in subs)),
          "proofs_deep_subclass": deep, "proofs_package": pkg,
          "proofs_binding": {f"{a} {b}": p for (a, b), p in sorted(kinds.items())},
          "proofs_wrong": wrong, "missed_by_kind": dict(miss),
          "rules_law": [x.text for x in rules if x.tier == "law" and "TREE" not in x.text][:40],
          "rules_tree_binding": [{"text": x.text, "tier": x.tier, "known": x.known, "agree": x.agree} for x in rules
                                 if "TREE" in x.text and "is bound to ?](a," in x.text and "has" in x.text.split("&")[1]]}
    json.dump(sc, open(os.path.join(STUDY, "showcase.json"), "w"), indent=1, default=str)
    print(sc["tiers"], sc["hops_histogram"], sc["missed_by_kind"])


if __name__ == "__main__":
    main()
