"""Exp 3: is the full rebuild after every ingest actually a problem? (a) where the time goes, (b) interactive
ingest-one-fact-then-ask latency, (c) how stable the accepted rule set is as data streams in."""
import subprocess, time, random, re, json, statistics as st
from harness import *
res = {}
for scale in (1, 4, 8):
    T, E = generate(0, scale); lines, info = observe(T, E, 0, 0.5, n_unseen=25 * scale, n_sparse=50 * scale)
    path = f"{DATA}/obs_scale{scale}.txt"; open(path, "w").write("\n".join(lines) + "\n")
    out = subprocess.run([EXP], input=f"SET PROFILE 1\nINGESTFILE {path}\nINFER\nEXIT\n", capture_output=True, text=True).stdout
    prof = dict((k.strip(), float(v)) for k, v in re.findall(r"(classes|relations|rule mining|infer) ([\d.]+) ms", out))
    # interactive: 20 cycles of (ingest one new fact, ask one question), timed from outside through a live session
    held = [f"{a} {p} {b}" for p, fs in T.items() for a, b in fs][:20]
    p = subprocess.Popen(["stdbuf", "-oL", EXP], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    def cmd(c):
        p.stdin.write(c + "\nFIND __m__\n"); p.stdin.flush()
        while not p.stdout.readline().startswith("[FIND] not stored"): pass
    cmd(f"INGESTFILE {path}"); cmd("INFER")
    lat = []
    for f in held:
        t = time.perf_counter(); cmd(f"INGEST {f}"); cmd(f"ASK {f.split()[0]} lives in ?"); lat.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter(); [cmd(f"ASK {f.split()[0]} lives in ?") for f in held]; ask_only = (time.perf_counter() - t) * 1000 / len(held)
    p.stdin.write("EXIT\n"); p.stdin.flush(); p.wait()
    res[scale] = {"facts": len(lines), "profile_ms": prof, "ingest+ask_ms_mean": st.mean(lat), "ask_without_ingest_ms": ask_only}
    print(scale, json.dumps(res[scale]))
# (c) rule stability over a stream (scale 1, 50% coverage, seeds 0-2): accepted rules after 10..100% of the data
stab = {}
for seed in range(3):
    w = world(seed, 0.5); lines = open(w["path"]).read().splitlines(); r = random.Random(seed); r.shuffle(lines)
    final = None; sets = {}
    for frac in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0):
        part = f"{DATA}/stream_{seed}.txt"; open(part, "w").write("\n".join(lines[:int(frac * len(lines))]) + "\n")
        out = subprocess.run([EXP], input=f"SET COV 2\nINGESTFILE {part}\nRELATIONS\nEXIT\n", capture_output=True, text=True).stdout
        sets[frac] = {(x["type"], x["r1"], x["r2"], x["r3"]) for x in parse_rules(out.splitlines()) if x["accepted"]}
    for frac, s in sets.items():
        j = len(s & sets[1.0]) / len(s | sets[1.0]) if s | sets[1.0] else 1
        stab.setdefault(frac, []).append(j)
print("rule-set similarity to the final rule set (Jaccard), by fraction of data seen:", {f: round(st.mean(v), 2) for f, v in stab.items()})
json.dump({"scales": res, "stability": stab}, open("results_exp3.json", "w"), indent=1)
