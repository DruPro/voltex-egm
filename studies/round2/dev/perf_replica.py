"""Performance diagnosis (D4): a reversed_weak-like world built from SPEC.md alone (not the generator), timed per
profile and per engine command. No confirmation data."""
import os, random, subprocess, sys, time
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
def world(seed=0, top=6, mid=(4, 6), leaf=(6, 9)):
    r = random.Random(seed); L = []; parent = {}; n = 0
    def nm(): 
        nonlocal n; n += 1; return f"pk{n}x"
    tops = [nm() for _ in range(top)]
    for t in tops:
        for _ in range(r.randint(*mid)):
            m = nm(); parent[m] = t
            for _ in range(r.randint(*leaf)):
                parent[nm()] = m
    anc = lambda a: ([parent[a]] + anc(parent[a])) if a in parent else []
    for a in parent:
        for i, b in enumerate(anc(a)):
            if i == 0 or r.random() < 0.7: L.append(f"{a} requires {b}")
    pairs = [(a, parent[a]) for a in parent]; ents = list(parent) + tops
    for a, b in pairs:
        if r.random() < 0.2: L.append(f"{b} suggests {a}")
        else: L.append(f"{r.choice(ents)} suggests {r.choice(ents)}")
    return sorted(set(L))
lines = world(); open("/tmp/rep.txt", "w").write("\n".join(lines) + "\n"); print(len(lines), "lines")
sys.path.insert(0, ROOT); from egm.policy import BUILTINS
tend = BUILTINS["tendency"].engine_command()
for b in sys.argv[1:] or [os.path.join(ROOT, "build/voltex2")]:
    for name, pre in (("default", []), ("ts0", ["SET TENDENCYSTEPS 0"]), ("covsource", ["SET COVSOURCE 1"])):
        inp = "\n".join(pre + ["INGESTFILE /tmp/rep.txt", "INFER ALL"]) + "\n"
        t = time.time(); r = subprocess.run([b], input=inp, capture_output=True, text=True, timeout=1800)
        print(f"{os.path.basename(b):14s} {name:10s} INFER ALL {time.time() - t:6.1f}s  {len(r.stdout.splitlines())} lines", flush=True)
