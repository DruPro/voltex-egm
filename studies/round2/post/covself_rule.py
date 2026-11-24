"""Demo: the self-sourced decoy on reversed_weak, with and without COVSELF (Round 2 sealed seeds, now development)."""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies/capability/tools"), os.path.join(ROOT, "studies/round2/confirm"), os.path.join(ROOT, "studies/sealed2")]
import confirm2, egm
w = confirm2.sealed_world("reversed_weak", 2000)
for fix in (0, 1):
    with egm.Engine(settings={"COVSOURCE": 1, "COVSELF": fix}) as e:
        e.ingest_many(w.lines); e.apply_policy("strict")
        print(f"COVSELF {fix}:")
        for r in e.evidence(include_rejected=True):
            if "suggests" in r["rule"].split("=>")[1] or "requires" in r["rule"].split("=>")[1] and r["rule"].count("&") == 0:
                if r["rule"].count("&") == 0:
                    print(f"   {'accepted' if r['accepted'] else 'rejected':8s} admit={r['admit']:9s} agree={r['agree']:.2f} cov={r['cov']:.2f} rel={r['rel']:.2f}  {r['rule']}")
