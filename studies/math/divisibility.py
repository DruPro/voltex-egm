"""Divisibility by example: half the 'divides' facts among 2..N are given; can transitivity recover the rest?"""
import random, subprocess, sys, os, tempfile
E = os.environ.get("VOLTEX", "/home/claude/work/egm-kit/build/voltex2"); N = int(os.environ.get("N", 60))
def nm(i): return f"n{i}"
for seed in range(int(os.environ.get("SEEDS", 3))):
    r = random.Random(seed)
    pairs = [(a, b) for a in range(2, N + 1) for b in range(2 * a, N + 1, a)]   # a divides b, a < b
    r.shuffle(pairs); shown = set(pairs[: len(pairs) // 2]); hidden = set(pairs[len(pairs) // 2 :])
    lines = [f"{nm(a)} divides {nm(b)}" for a, b in shown]
    path = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name; open(path, "w").write("\n".join(lines) + "\n")
    out = subprocess.run([E], input=f"INGESTFILE {path}\nRELATIONS\nINFER ALL\nEXIT\n", capture_output=True, text=True).stdout
    rules = [l.strip()[:110] for l in out.splitlines() if l.strip().startswith("ACCEPT")]
    d = {tuple(int(x[1:]) for x in l.split("\t")[1].split(" divides ")) for l in out.splitlines() if l.startswith("FACT\t") and " divides " in l}
    # which hidden facts are derivable at all from the shown facts by chaining? (closure of shown)
    clos = set(shown); changed = True
    while changed:
        changed = False
        for a, b in list(clos):
            for c in range(2 * b, N + 1, b):
                if (b, c) in clos and (a, c) not in clos: clos.add((a, c)); changed = True
    derivable = hidden & clos
    print(f"seed {seed}: rules {rules}")
    print(f"   hidden {len(hidden)} | derivable from the evidence {len(derivable)} | inferred correctly {len(d & hidden)} | wrong {len(d - hidden - shown)}")
