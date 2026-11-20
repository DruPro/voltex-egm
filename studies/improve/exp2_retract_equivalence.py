"""Invariant: ingest(all) + retract(subset) must answer exactly like ingest(all - subset). 5 worlds x 300 random facts."""
import random, subprocess
from harness import *
ok = 0
for seed in range(5):
    w = world(seed, 0.5); lines = [l for l in open(w["path"]).read().splitlines() if l]
    r = random.Random(seed); gone = set(r.sample(lines, 300))
    keep_path = f"{DATA}/keep_{seed}.txt"; open(keep_path, "w").write("\n".join(l for l in lines if l not in gone) + "\n")
    q = ["RELATIONS", "INFER ALL", "CONFLICTS", "CLASSES"]
    a = subprocess.run([EXP], input="\n".join([f"INGESTFILE {w['path']}"] + [f"RETRACT {l}" for l in sorted(gone)] + q + ["SAVE /tmp/r.vtx2", "LOAD /tmp/r.vtx2"] + q + ["EXIT"]) + "\n", capture_output=True, text=True).stdout
    b = subprocess.run([EXP], input="\n".join([f"INGESTFILE {keep_path}"] + q + ["SAVE /tmp/k.vtx2", "LOAD /tmp/k.vtx2"] + q + ["EXIT"]) + "\n", capture_output=True, text=True).stdout
    strip = lambda o: sorted(l for l in o.splitlines() if not l.startswith(("[INGEST]", "[RETRACT]", "[SAVE]", "[LOAD]", "  C")))
    same = strip(a) == strip(b); ok += same
    print(f"seed {seed}: retracted {a.count('[RETRACT] removed')} of 300 | answers identical to never-ingested: {same}")
print(f"retract-equivalence: {ok}/5")
