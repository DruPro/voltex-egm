"""Round 2 dev (W1): COVSOURCE 0 vs 1, and policies with/without minCoverageSourceAgreement, on development worlds."""
import json, os, random, statistics, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
T = os.path.join(ROOT, "studies/capability/tools")
sys.path[:0] = [ROOT, T, os.path.join(ROOT, "studies/evidence_policy/confirm")]
import egm, cworlds, metrics, realdata
from interface import EGMAdapter
from egm.policy import BUILTINS
import copy, dataclasses
def pol(name, **thr):
    p = BUILTINS[name]; ext = copy.deepcopy(p.extension)
    if ext: ext["thresholds"] = dict(ext["thresholds"], **thr)
    return dataclasses.replace(p, name=name + "-w1a", version="dev", builtin=False,
                               thresholds=dict(p.thresholds, **thr), extension=ext)
PROF = {"default": lambda: EGMAdapter({}), "default+COVSRC": lambda: EGMAdapter({"COVSOURCE": 1}),
        "strict": lambda: EGMAdapter(policy="strict"), "strict+COVSRC": lambda: EGMAdapter({"COVSOURCE": 1}, policy="strict"),
        "tendency": lambda: EGMAdapter(policy="tendency"), "tendency+COVSRC": lambda: EGMAdapter({"COVSOURCE": 1}, policy="tendency"),
        "tendency+W1a.5": lambda: EGMAdapter(policy=pol("tendency", minCoverageSourceAgreement=0.5))}
worlds = [c[0] for c in cworlds.CATALOGUE] + ["dpkg"]
out = {}
for wn in (sys.argv[1:] or worlds):
    for s in (range(5) if wn != "dpkg" else range(1000, 1005)):
        w = realdata.load(wn, s) if wn == "dpkg" else cworlds.load(wn, s)
        for pn, mk in PROF.items():
            e = mk(); 
            if wn == "dpkg": e.settings["MAXWORDS"] = w.maxwords
            m = metrics.measure(w, e.run(w.lines, w.rels, []))
            out.setdefault(wn, {}).setdefault(pn, []).append({k: m.get(k) for k in ("precision", "recall", "new", "aurc")})
    print(wn, flush=True)
    for pn, ms in out[wn].items():
        f = lambda k: (lambda xs: "%.3f" % statistics.mean(xs) if xs else "undef")([x[k] for x in ms if x[k] is not None])
        print("   %-16s prec %s  rec %s  new %s  aurc %s" % (pn, f("precision"), f("recall"), f("new"), f("aurc")), flush=True)
json.dump(out, open(os.path.join(os.path.dirname(__file__), os.environ.get("OUT", "w1_compare.json")), "w"), indent=1)
