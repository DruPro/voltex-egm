"""W2 hypothesis check: does the subject bootstrap flag the dpkg flood within one split (COVSOURCE 0)?"""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies/capability/tools"), os.path.join(ROOT, "studies/evidence_policy/confirm")]
import egm, realdata, time
for seed in range(1000, 1005):
    w = realdata.load("dpkg", seed); t = time.time()
    with egm.Engine(binary=os.path.join(ROOT, "build/voltex2"), settings={"MAXWORDS": w.maxwords}) as e:
        e.ingest_many(w.lines); ev = e.evidence()
    print("split", seed, "%.0fs" % (time.time() - t))
    for r in ev: print("   stab=%s agree=%s rel=%.2f %s" % (r["stability"], r["agree"], r["rel"], r["rule"][:90]))
