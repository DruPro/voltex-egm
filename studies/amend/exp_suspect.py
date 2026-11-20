"""H4: does SUSPECT flag implausible amendments without flagging legitimate ones? (PREREGISTRATION.md)"""
import sys, re, json, random, subprocess
sys.path.insert(0, "/home/claude/work/improve")
from harness import world
AM = "/home/claude/work/amend/voltex2_amend"
rows = []
for seed in [1, 2, 3, 4, 5]:
    w = world(seed, 0.5); T, E, obs = w["T"], w["E"], set(w["observed"])
    wrong = {x[1] for x in w["info"]["wrong"]}
    region = dict(map(tuple, T["is located in"]))
    tl, tw, tf = dict(map(tuple, T["lives in"])), dict(map(tuple, T["works as"])), dict(map(tuple, T["is from"]))
    st = lambda pred: {a: b for (p, a, b) in obs if p == pred and a not in wrong}
    sl, sw, sf, sloc = st("lives in"), st("works as"), st("is from"), st("is located in")
    rng = random.Random(seed * 101)
    odd = rng.sample(sorted(set(sl) & set(sf)), 25)
    rest = sorted((set(sl) & set(sw)) - set(odd)); sample = rng.sample(rest, 40) + odd
    cases = []
    for p in sample[:20]:   # legitimate: move (new region)
        cases.append(("legit_move", f"{p} lives in {rng.choice([s for s in E['settlement'] if region[s] != region[sl[p]]])}", f"{p} lives in {sl[p]}"))
    for p in sample[20:40]:  # legitimate: career change
        cases.append(("legit_job", f"{p} works as {rng.choice([j for j in E['profession'] if j != sw[p]])}", f"{p} works as {sw[p]}"))
    for p in sample[40:65]:  # implausible: region of origin changed while residence still says otherwise
        cases.append(("odd_from", f"{p} is from {rng.choice([g for g in E['region'] if g != sf[p]])}", f"{p} is from {sf[p]}"))
    for s in rng.sample(sorted(sloc), min(15, len(sloc))):  # implausible: a settlement changes region
        cases.append(("odd_loc", f"{s} is located in {rng.choice([g for g in E['region'] if g != sloc[s]])}", f"{s} is located in {sloc[s]}"))
    rng.shuffle(cases)
    cmds = ["SET EXPLAIN 0", "SET SUSPECT 1", f"INGESTFILE {w['path']}"] + [f"AMEND {c[1]}" for c in cases] + ["EXIT"]
    out = subprocess.run([AM], input="\n".join(cmds) + "\n", capture_output=True, text=True).stdout
    open(f"/home/claude/work/amend/logs/suspect_s{seed}.log", "w").write(out)
    sus = {}
    for l in out.splitlines():
        m = re.match(r"\[SUSPECT\] law=(\d+) any=(\d+)\t(.*)", l)
        if m: sus[m.group(3)] = (int(m.group(1)), int(m.group(2)))
    for kind, new, old in cases:
        L, N = sus.get(old, (None, None))
        rows.append({"seed": seed, "kind": kind, "old": old, "checked": L is not None, "law": L or 0, "any": N or 0})
json.dump(rows, open("/home/claude/work/amend/results_suspect.json", "w"), indent=1)
print(f"{'kind':12} {'n':>4} {'checked':>7} {'flag law':>8} {'flag any':>8}")
for k in ["legit_move", "legit_job", "odd_from", "odd_loc"]:
    R = [r for r in rows if r["kind"] == k]
    print(f"{k:12} {len(R):4} {sum(r['checked'] for r in R):7} {sum(r['law'] > 0 for r in R) / len(R):8.3f} {sum(r['any'] > 0 for r in R) / len(R):8.3f}")
for grp, ks in [("legitimate", ["legit_move", "legit_job"]), ("implausible", ["odd_from", "odd_loc"])]:
    R = [r for r in rows if r["kind"] in ks]
    print(f"{grp:12} {len(R):4} {'':7} {sum(r['law'] > 0 for r in R) / len(R):8.3f} {sum(r['any'] > 0 for r in R) / len(R):8.3f}")
