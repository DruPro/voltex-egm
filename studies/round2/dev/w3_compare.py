"""Round 2 dev (W3): CONDITIONS 1 with CONDHOLDOUT 0 vs 1 (COVSOURCE 1 throughout). Development worlds only:
Round 1 development worlds and Round 1 sealed conditional worlds (seeds 1000-1004, now development)."""
import json, os, statistics, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies/capability/tools"), os.path.join(ROOT, "studies/evidence_policy/confirm"), os.path.join(ROOT, "studies/sealed")]
import egm, cworlds, metrics, confirm
from interface import EGMAdapter
B = {"COVSOURCE": 1, "CONDITIONS": 1}
PROF = {"default": {}, "default+HO": {"CONDHOLDOUT": 1}}
POL = {"default": None, "strict": "strict", "tendency": "tendency"}
WORLDS = [("harvest", range(5)), ("hidden-cov30", range(5)), ("hidden-cov50", range(5)), ("hidden-cov70", range(5)),
          ("conditional", range(1000, 1005)), ("conditional_decoy", range(1000, 1005)), ("conditional_control", range(1000, 1005))]
out = {}
for wn, seeds in WORLDS:
    conds = {}
    for s in seeds:
        w = confirm.sealed_world(wn, s) if wn.startswith("conditional") else cworlds.load(wn, s)
        for hn, hs in PROF.items():
            for pn, pol in POL.items():
                e = EGMAdapter({**B, **hs}, policy=pol)
                m = metrics.measure(w, e.run(w.lines, w.rels, []))
                out.setdefault(wn, {}).setdefault(f"{pn}{'+HO' if hs else ''}", []).append({k: m.get(k) for k in ("precision", "recall", "new", "aurc")})
            with egm.Engine(binary=os.path.join(ROOT, "build/voltex2"), settings={**B, **hs}) as e:
                e.ingest_many(w.lines)
                for r in e.evidence():
                    if " if " in r["rule"]:
                        c = r["rule"].split(" if ")[1].split("(")[0]
                        conds.setdefault(hn, {}).setdefault(c, 0); conds[hn][c] += 1
    print(wn, " conditions learned (relation: rules x seeds):", conds, flush=True)
    for pn, ms in out[wn].items():
        f = lambda k: (lambda xs: "%.3f" % statistics.mean(xs) if xs else "undef")([x[k] for x in ms if x[k] is not None])
        print("   %-12s prec %s  rec %s  new %s  aurc %s" % (pn, f("precision"), f("recall"), f("new"), f("aurc")), flush=True)
json.dump(out, open(os.path.join(os.path.dirname(__file__), os.environ.get("OUT", "w3_iter1.json")), "w"), indent=1)
