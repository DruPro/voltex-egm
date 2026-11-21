"""Runs voltex2 on a generated company and scores every inferred fact against the ground truth.
Usage: python3 evaluate.py <dir> [binary]"""
import json, subprocess, sys, collections
d = sys.argv[1]; binary = sys.argv[2] if len(sys.argv) > 2 else "../v2/voltex2"
truth = json.load(open(f"{d}/truth.json"))
T = {k: {tuple(x) for x in v} for k, v in truth["truth"].items()}
S = {k: {tuple(x) for x in v} for k, v in truth["stated"].items()}
import os
cmds = f"INGESTFILE {d}/facts.txt\n{os.environ.get('EXTRA', '')}METRICS\nRELATIONS\nINFER ALL\nCONFLICTS\nEXIT\n"
out = subprocess.run([binary], input=cmds, capture_output=True, text=True).stdout
open(f"{d}/run.log", "w").write(out)
rels = sorted(T, key=len, reverse=True)
derived = collections.defaultdict(set)
for line in out.splitlines():
    if not line.startswith("FACT\t"): continue
    f = line.split("\t")[1]
    for rel in rels:
        if f" {rel} " in f:
            a, b = f.split(f" {rel} "); derived[rel].add((a.strip(), b.strip())); break
rows = []; tot_d = tot_ok = 0
for rel in T:
    missing = T[rel] - S[rel]; got = derived.get(rel, set())
    ok = len(got & T[rel]); tot_d += len(got); tot_ok += ok
    rows.append((rel, len(missing), len(got & missing), len(got), ok))
print(f"{'relation':20} {'unstated true':>13} {'recovered':>10} {'derived':>8} {'correct':>8}")
for rel, m, rec, g, ok in rows:
    print(f"{rel:20} {m:13} {rec:10} {g:8} {ok:8}" + (f"   recall {rec / m:.0%}" if m else "") + (f"   precision {ok / g:.0%}" if g else ""))
print(f"ALL derived {tot_d}, correct {tot_ok}" + (f" -> precision {tot_ok / tot_d:.1%}" if tot_d else ""))
print("\n".join(l for l in out.splitlines() if l.strip().startswith(("ACCEPT", "reject"))))
conf = [l for l in out.splitlines() if l.startswith("CONFLICT\t")]
if truth["corrupted"] or conf:
    bad = {(a, w) for a, _, w in truth["corrupted"]}
    flagged = set()
    for l in conf:
        _, subj, stated_obj = l.split("\t")[:3]; flagged.add((subj, stated_obj))
    hit = len(flagged & bad)
    print(f"NOISE: {len(bad)} corrupted facts | {len(flagged)} flagged as conflicts | {hit} of the flags are real corruptions "
          f"(recall {hit / max(1, len(bad)):.0%}, precision {hit / max(1, len(flagged)):.0%})")
