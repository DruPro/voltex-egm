"""Spike 1: EGM's conflicts on 'ends with' are its leak reports. Prints each, with how the handle escapes."""
import sys, os, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
import egm
lines = [l for l in open(sys.argv[1] if len(sys.argv) > 1 else "facts.txt").read().split("\n") if l]
esc = collections.defaultdict(set)
for l in lines:
    if " escapes via " in l: esc[l.split()[0]].add(l.split()[-1])
for st in ({"TREES": 1},):
    with egm.Engine(settings=st) as e:
        e.ingest_many(lines); e.infer_all()
        cs = [c for c in e.conflicts() if " ends with " in c.detail]
        print(f"=== {st or 'default'}: {len(cs)} reports")
        for c in cs:
            should = c.detail.split("inferred: ")[1].split(" |")[0].split()[-1]
            print(f"   {c.subject:22s} code ends with {c.stated:10s} escapes via {','.join(sorted(esc[c.subject])):7s} -> EGM expects {should}")
