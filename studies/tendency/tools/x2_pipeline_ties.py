"""X2 (EXPLORATORY, after T7 failed): T7's pipeline kept every tied value, so a subject reported 1x/1x/1x got three
values and the relation stopped looking one-value. Variant: on a tie, keep none (the value is unknown, as the data
cannot decide). Same cells as T7. Writes results_x2.json."""
import collections, json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "noise", "tools"))
import lib
from run_all import ONE_VALUE


def pipeline_majority_strict(lines, rels, one_value):
    count = collections.Counter(); keep = []
    for l in lines:
        f = lib.parse_fact(l, rels)
        if f and f[0] in one_value: count[f] += 1
        else: keep.append(l)
    best = collections.defaultdict(list)
    for (r, a, b), n in count.items(): best[(r, a)].append((n, b))
    for (r, a), vs in best.items():
        vs.sort(reverse=True)
        if len(vs) == 1 or vs[0][0] > vs[1][0]: keep.append(f"{a} {r} {vs[0][1]}")
    return sorted(set(keep))


rows = []
for w in ("company", "hidden"):
    for nz in (0.15, 0.30):
        for rp in (3, 5):
            for s in range(5):
                kw = dict(scale=1.0, noise=nz, reports=rp) if w == "company" else dict(scale=1, coverage=0.5, noise=nz, reports=rp)
                obs, hid = lib.world(w, seed=s, **kw)
                rels = sorted(hid["relations"], key=len, reverse=True)
                lines = pipeline_majority_strict(open(obs).read().splitlines(), rels, ONE_VALUE[w])
                with tempfile.TemporaryDirectory() as td:
                    p = os.path.join(td, "f.txt"); open(p, "w").write("\n".join(lines) + "\n")
                    r = lib.score(lib.run(p, []), obs, hid)
                rows.append({"world": w, "noise": nz, "reports": rp, "seed": s, **{k: r[k] for k in ("derived_new", "correct", "wrong", "precision", "recall")}})
                print(rows[-1], flush=True)
json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_x2.json"), "w"), indent=1)
