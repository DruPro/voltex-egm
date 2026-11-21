"""Modular arithmetic by example: remainders mod 3 for half the numbers, plus 'is three more than' and a decoy 'is one more than'.
Can the engine compute the missing remainders, and pick the right relation?"""
import random, subprocess, os, tempfile
E = os.environ.get("VOLTEX", "/home/claude/work/egm-kit/build/voltex2"); N = int(os.environ.get("N", 90))
def nm(i): return f"n{i}"
tot = [0, 0, 0, 0]
for seed in range(5):
    r = random.Random(seed)
    nums = list(range(N)); r.shuffle(nums); taught = set(nums[: N // 2]); unseen = set(nums[N // 2 :])
    lines = [f"{nm(a + 3)} is three more than {nm(a)}" for a in range(N - 3)]
    lines += [f"{nm(a + 1)} is one more than {nm(a)}" for a in range(N - 1)]          # decoy: true, but irrelevant to mod 3
    lines += [f"{nm(a)} has remainder r{a % 3}" for a in sorted(taught)]
    path = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False).name; open(path, "w").write("\n".join(lines) + "\n")
    out = subprocess.run([E], input=f"INGESTFILE {path}\nRELATIONS\nINFER ALL\nEXIT\n", capture_output=True, text=True).stdout
    acc = [l.strip() for l in out.splitlines() if l.strip().startswith("ACCEPT")]
    got = {}
    for l in out.splitlines():
        if l.startswith("FACT\t") and " has remainder " in l:
            a, rr = l.split("\t")[1].split(" has remainder "); got[int(a[1:])] = int(rr[1:])
    right = sum(1 for a in unseen if got.get(a) == a % 3); wrong = sum(1 for a, v in got.items() if v != a % 3)
    tot[0] += right; tot[1] += len(unseen); tot[2] += wrong; tot[3] += len(got)
    if seed == 0:
        for a in acc: print(a[:150])
print(f"unseen numbers: remainder computed correctly for {tot[0]}/{tot[1]} | wrong {tot[2]} (5 seeds, numbers 0..{N-1})")
