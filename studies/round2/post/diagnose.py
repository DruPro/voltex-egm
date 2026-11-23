"""Post-hoc (after the confirmation results were published): which admitted rules produce strict's wrong answers.
Exploratory; decides nothing that the pre-registration fixed."""
import collections, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path[:0] = [ROOT, os.path.join(ROOT, "studies/capability/tools"), os.path.join(ROOT, "studies/round2/confirm"), os.path.join(ROOT, "studies/sealed2")]
import confirm2, realdata2, cworlds
from interface import EGMAdapter
import egm
cases = [("reversed_weak", 2000, {"COVSOURCE": 1}, "strict"), ("c_headers", 2000, {"COVSOURCE": 1}, "strict"),
         ("services", 2000, {"COVSOURCE": 1}, "tendency")]
for name, seed, st, pol in cases:
    w = confirm2.sealed_world(name, seed) if name in confirm2.STRUCTURES else realdata2.load(name, seed)
    if name not in confirm2.STRUCTURES: st = {**st, "MAXWORDS": w.maxwords}
    run = EGMAdapter(st, policy=pol).run(w.lines, w.rels, []); S = cworlds.stated(w)
    by = collections.defaultdict(lambda: [0, 0])
    for a in run.answers:
        if a.status == "derived" and a.fact not in S:
            by[a.rule][0] += 1; by[a.rule][1] += a.fact in w.truth
    print(f"== {name} {seed} {st} {pol}")
    with egm.Engine(settings=st) as e:
        e.ingest_many(w.lines); e.apply_policy(pol); ev = {v["rule"]: v for v in e.evidence()}
    for rule, (n, ok) in sorted(by.items(), key=lambda x: -x[1][0])[:6]:
        v = ev.get(rule, {})
        print(f"  {n:6d} new, {ok/n:.2f} true | agree={v.get('agree')} rel={v.get('rel')} cov={v.get('cov')} src={v.get('cov_source')}/{v.get('cov_source_agree')} stab={v.get('stability')} admit={v.get('admit')} | {rule[:120]}")
    wrong = [a.fact for a in run.answers if a.status == "derived" and a.fact not in S and a.fact not in w.truth][:3]
    print("  e.g. wrong:", wrong)
