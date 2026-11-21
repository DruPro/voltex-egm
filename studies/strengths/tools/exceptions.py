"""Hidden binding facts by kind (scope, decorator): right, wrong (by tier) or unanswered, with round 3 `full`
settings, for the stdlib (obs_r2) and the replication (obs_dist).  python3 exceptions.py -> ../results_*/exceptions.json"""
import collections, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
for obs, out, mw in (("obs_r2", "results_r3", 28500), ("obs_dist", "results_dist", 72600)):
    o = os.path.join(STUDY, obs); t = json.load(open(os.path.join(o, "truth.json")))
    rel = collections.defaultdict(dict)
    for f in t["base"]:
        s, _, rest = f.partition(" "); r, v = rest.rsplit(" ", 1); rel[r][s] = v
    stated = {l.strip() for l in open(os.path.join(o, "facts.txt"))}
    key = [l.strip() for l in open(os.path.join(o, "key.txt")) if " is bound to " in l]
    st = {"MAXWORDS": mw, "TENDENCYSTEPS": 0, "TREES": 1, "CHAIN": 3, "DEPTH": 0}
    with egm.open(os.path.join(o, "facts.txt"), settings=st, binary=os.path.join(ROOT, "build", "voltex2")) as e:
        got = {}
        for f in e.infer_all():
            n = " ".join(f.fact.split())
            if " is bound to " in n and n not in stated: got.setdefault(n.split()[0], []).append((n, f.tier))
    c = collections.defaultdict(collections.Counter)
    for k in key:
        s = k.split()[0]; fn = s[:-4]; kind = f"{rel['has scope'][fn]} {rel['has decorator'][fn]}"
        g = got.get(s, [])
        if any(n == k for n, _ in g): c[kind]["right"] += 1
        elif g: c[kind]["wrong " + g[0][1]] += 1
        else: c[kind]["unanswered"] += 1
    res = {"settings": st, "by_kind": {k: dict(v) for k, v in sorted(c.items())}}
    json.dump(res, open(os.path.join(STUDY, out, "exceptions.json"), "w"), indent=1); print(obs, res["by_kind"])
