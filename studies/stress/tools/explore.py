"""Exploratory (no verdicts): what did the engine learn from each bench dataset, and how does it reason?

  python3 explore.py [DATASET[:K=V,K=V] ...]   writes ../explore/<dataset>[__settings].json

Per run: accepted rules (text, shape, tier, n, k, rate, lift, known, agree), derived facts split by whether they are in
the hidden key (recovered held-out truth) or not, proof examples (because + rule) for recovered facts, and the
distribution of proof rounds and tendency steps (chains()).
"""
import collections, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
OBS = os.path.join(STUDY, "obs"); OUT = os.path.join(STUDY, "explore")
BIN = os.path.join(ROOT, "build", "voltex2")


def norm(s): return " ".join(s.split())


def prepare_realcode():
    """Real code with cross-module resolution: the repo's own extractor output (studies/shard_general/data), 20% held
    out with bench.held_out. Not in the pre-registered manifest; exploratory only."""
    p = os.path.join(OBS, "code_realcode.txt")
    if os.path.exists(p): return
    import lzma; sys.path.insert(0, HERE); import bench
    with lzma.open(os.path.join(ROOT, "studies", "shard_general", "data", "realcode_facts.txt.xz"), "rt") as fh:
        facts = sorted({l.strip() for l in fh if l.strip()})
    s, k = bench.held_out(facts, 11)
    open(p, "w").write("\n".join(s) + "\n"); open(os.path.join(OBS, "keys", "code_realcode.key"), "w").write("\n".join(k) + "\n")


def proof(e, fact, depth=0, seen=None):
    """Expand a derived fact into its proof tree by asking for each premise (stated premises are leaves)."""
    seen = seen if seen is not None else set()
    if depth > 5 or fact in seen: return {"fact": fact, "stated": None}
    seen.add(fact)
    sub, _, _ = fact.partition(" ")
    for f in e.ask(fact.rsplit(" ", 1)[0] + " ?"):
        if norm(f.fact) == norm(fact):
            if f.status == "stated" or not f.because: return {"fact": fact, "stated": True}
            return {"fact": fact, "stated": False, "tier": f.tier, "rule": f.rule,
                    "because": [proof(e, b, depth + 1, seen) for b in f.because]}
    return {"fact": fact, "stated": None}


def explore(name, settings):
    if name == "code_realcode": prepare_realcode()
    words = len({w for l in open(os.path.join(OBS, name + ".txt")) for w in l.split()})
    st = dict(settings)
    if words > 11000: st.setdefault("MAXWORDS", words + 1000)
    key = {norm(l) for l in open(os.path.join(OBS, "keys", name + ".key")) if l.strip()}
    stated = {norm(l) for l in open(os.path.join(OBS, name + ".txt")) if l.strip()}
    with egm.open(os.path.join(OBS, name + ".txt"), settings=st, binary=BIN) as e:
        rules = [r for r in e.rules()]
        facts = e.infer_all()
        chains = e.chains()
        rels = e.relations()
        rnd_of = {norm(c["fact"]): (c.get("round"), c.get("tendency_steps")) for c in chains}
        rr = random.Random(7)
        hit0 = [f for f in facts if norm(f.fact) in key]
        deep = [f for f in hit0 if (rnd_of.get(norm(f.fact)) or (0,))[0] and rnd_of[norm(f.fact)][0] >= 2]
        trees = [proof(e, f.fact) for f in rr.sample(deep, min(6, len(deep)))]
        shallow = [proof(e, f.fact) for f in rr.sample(hit0, min(10, len(hit0)))]
        wrong0 = [f for f in facts if norm(f.fact) not in key and norm(f.fact) not in stated]
        wrong_trees = [proof(e, f.fact) for f in rr.sample(wrong0, min(4, len(wrong0)))]
    new = [f for f in facts if norm(f.fact) not in stated]
    hit = [f for f in new if norm(f.fact) in key]
    miss = [f for f in new if norm(f.fact) not in key]
    rnd = collections.Counter((c.get("round"), c.get("tendency_steps")) for c in chains)
    out = {"dataset": name, "settings": st, "stated": len(stated), "key": len(key), "derived_new": len(new),
           "recovered": len(hit), "not_in_key": len(miss),
           "relations": [{"relation": x.relation, "facts": x.facts} for x in rels],
           "rules": [{"text": x.text, "shape": x.shape, "tier": x.tier, "n": x.n, "k": x.k, "rate": x.rate, "lift": x.lift,
                      "known": x.known, "agree": x.agree}
                     for x in rules],
           "rounds": [{"round": k[0], "tendency_steps": k[1], "facts": v} for k, v in sorted(rnd.items(), key=str)],
           "proofs_recovered": shallow, "proofs_deep": trees, "proofs_not_in_key": wrong_trees}
    os.makedirs(OUT, exist_ok=True)
    tag = name + ("__" + "_".join(f"{k}{v}" for k, v in sorted(settings.items())) if settings else "")
    json.dump(out, open(os.path.join(OUT, tag + ".json"), "w"), indent=1, default=str)
    print(f"{tag:40s} stated={len(stated)} new={len(new)} recovered={len(hit)} rules={len(rules)}", flush=True)
    return out


if __name__ == "__main__":
    for a in sys.argv[1:]:
        name, _, s = a.partition(":")
        st = dict(kv.split("=") for kv in s.split(",")) if s else {}
        explore(name, st)
