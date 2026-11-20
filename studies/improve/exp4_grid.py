"""Exp 4 grid: can ANY threshold on the representativeness ratio separate a conditional rule from a sparsely stated law?
Rule under test: member of(p,g) & group uses(g,i) => person uses(p,i).
  q = fraction of people the rule really applies to (1.0 = law, <1 = conditional)
  s = how often the conclusion 'person uses' is stated when true
Other relations are observed at 60%. Independent of the blind/company worlds (no tuning on test data)."""
import random, subprocess, json, re, sys
sys.path.insert(0, "/home/claude/work/blind")
from lib import parse_rules
EXP = "/home/claude/work/improve/voltex2_exp"
def make(q, s, seed):
    r = random.Random(seed); P = [f"p{i}x" for i in range(600)]; G = [f"g{i}y" for i in range(100)]; I = [f"item{i}z" for i in range(12)]
    grp = {p: r.choice(G) for p in P}; uses = {g: set(r.sample(I, 2)) for g in G}; applies = {p: r.random() < q for p in P}
    lines = []
    for p in P:
        if r.random() < 0.6: lines.append(f"{p} member of {grp[p]}")
        if r.random() < 0.6: lines.append(f"{grp[p]} has member {p}")
        if applies[p]:
            for i in uses[grp[p]]:
                if r.random() < s: lines.append(f"{p} person uses {i}")
    for g in G:
        for i in uses[g]:
            if r.random() < 0.6: lines.append(f"{g} group uses {i}")
    r.shuffle(lines); path = f"/tmp/grid_{q}_{s}_{seed}.txt"; open(path, "w").write("\n".join(lines) + "\n")
    return path
rows = []
for q in (1.0, 0.6, 0.3, 0.15):
    for s in (0.15, 0.3, 0.6):
        for seed in range(3):
            path = make(q, s, seed)
            res = {}
            for name, sets in [("frozen", []), ("REP0.5", ["COV 1", "REP 1"]), ("REP0.3", ["COV 1", "REP 1", "REPMIN 0.3"])]:
                out = subprocess.run([EXP], input="\n".join([f"SET {x}" for x in sets] + [f"INGESTFILE {path}", "RELATIONS", "EXIT"]) + "\n",
                                     capture_output=True, text=True).stdout
                rr = [x for x in parse_rules(out.splitlines()) if x["r1"] == "member of" and x["r2"] == "group uses" and x["r3"] == "person uses"]
                cov = re.search(r"global ([-\d.]+)", out)
                if rr:
                    x = rr[0]; res[name] = x["accepted"]
                    res["known_frac"] = x["known"] / x["n"] if x["n"] else 0; res["agree"] = x["agree"]
                    res["ratio"] = res["known_frac"] / float(cov.group(1)) if cov and float(cov.group(1)) > 0 else None
                else: res[name] = False
            rows.append({"q": q, "s": s, "seed": seed, **res})
json.dump(rows, open("results_exp4_grid.json", "w"), indent=1)
print(f"{'q (applies)':>11} {'s (stated)':>10} {'agree':>6} {'known/n':>8} {'ratio':>6} {'frozen':>7} {'REP0.5':>7} {'REP0.3':>7}   want")
for q in (1.0, 0.6, 0.3, 0.15):
    for s in (0.15, 0.3, 0.6):
        R = [r for r in rows if r["q"] == q and r["s"] == s]
        m = lambda k: sum(r.get(k) or 0 for r in R) / len(R)
        acc = lambda k: f"{sum(bool(r.get(k)) for r in R)}/3"
        print(f"{q:>11} {s:>10} {m('agree'):>6.2f} {m('known_frac'):>8.2f} {m('ratio'):>6.2f} {acc('frozen'):>7} {acc('REP0.5'):>7} {acc('REP0.3'):>7}   {'accept' if q == 1.0 else 'reject'}")
