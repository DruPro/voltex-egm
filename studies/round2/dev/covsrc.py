"""Round 2 dev: for each dpkg split, the coverage estimate's source and the rules that conclude the same relation."""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies/capability/tools"), os.path.join(ROOT, "studies/evidence_policy/confirm")]
import egm, realdata
for seed in range(1000, 1005):
    w = realdata.load("dpkg", seed)
    with egm.Engine(binary=os.path.join(ROOT, "build/voltex2"), settings={"MAXWORDS": w.maxwords, **({"COVSOURCE": 1} if os.environ.get("COVSRC") else {})}) as e:
        e.ingest_many(w.lines)
        ev = e.evidence(include_rejected=True)
        print("split", seed)
        for r in ev:
            if "depends on" in r["rule"].split("=>")[-1] and r["accepted"]:
                print("  %s %-70s n=%d k=%d agree=%s rate=%.3f lift=%.1f cov=%.3f rel=%.2f" % ("A" if r["accepted"] else "-",
                      r["rule"][:70], r["n"], r["e_plus"], r["agree"], r["e_plus"] / max(1, r["n"]), r["lift"], r["cov"], r["rel"]) + "  src=%s/%s" % (r["cov_source"], r["cov_source_agree"]))
        acc = [r for r in ev if r["accepted"]]
        print("  accepted %d; cov sources: %s" % (len(acc), sorted({(r["rule"].split("=>")[-1].strip()[:30], r["cov_source"], round(r["cov"], 3)) for r in acc})))
