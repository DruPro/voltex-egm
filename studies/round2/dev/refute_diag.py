"""Which rules exceed which coverage estimate (COVSOURCE 0 evidence), per world."""
import math, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies/capability/tools")]
import egm, cworlds
wn, s = sys.argv[1], int(sys.argv[2])
w = cworlds.load(wn, s)
with egm.Engine(binary=os.path.join(ROOT, "build/voltex2")) as e:
    e.ingest_many(w.lines); ev = e.evidence(include_rejected=True)
    for l in e._checked("RULES"):
        if "COVERAGE" in l: print(l)
concl = lambda r: r["rule"].split("=>")[-1].strip().split("(")[0]
for r in ev:
    if r["cov"] <= 0 or r["e_plus"] < 3: continue
    c = r["cov"]; n, k = r["n"], r["e_plus"]; z = (k - n * c) / math.sqrt(max(1e-9, n * c * (1 - c)))
    if z > 3: print("%s z=%.1f rate=%.3f cov=%.3f src=%s/%s n=%d %s" % ("A" if r["accepted"] else "-", z, k / n, c, r["cov_source"], r["cov_source_agree"], n, r["rule"][:110]))
