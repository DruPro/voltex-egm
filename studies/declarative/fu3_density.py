"""FU3 (exploratory): contradiction density at which each condition stops applying amendments to 'lives in'."""
import sys, json, collections, random
sys.argv = sys.argv[:1]
exec(open("/home/claude/work/declarative/exp_decl.py").read().rsplit('if __name__', 1)[0])
rows = []
for seed in [1, 2, 3, 4, 5]:
    w = world(seed, 0.5); obs = set(w["observed"]); info = w["info"]; tl = dict(map(tuple, w["T"]["lives in"]))
    stated = collections.defaultdict(set)
    for (p, a, b) in obs:
        if p == "lives in": stated[a].add(b)
    wrong = {x[1] for x in info["wrong"]}
    elig = sorted(a for a, v in stated.items() if v == {tl.get(a)} and a not in wrong and a not in info["sparse"])
    rng = random.Random(seed * 3 + 9); rng.shuffle(elig)
    changers = elig[:20]; pool = elig[20:]
    for dens in [0.05, 0.10, 0.15, 0.20]:
        nE = round(dens * len(stated)); contra = pool[:nE]
        ids = Ids(); evs = [(x, tl[x], rng.choice([s for s in w["E"]["settlement"] if s != tl[x]]), ids()) for x in changers]
        bogus = {x: rng.choice([s for s in w["E"]["settlement"] if s != tl[x]]) for x in contra}
        for cond in ["A", "B", "C2", "C2fn"]:
            cmds = [f"INGESTFILE {w['path']}"] + [c for x in contra for c in ev_plain(cond, x, "lives in", bogus[x])]
            for x, a, b, e in evs: cmds += ev_change(cond, x, "lives in", a, b, e)
            out, _ = run(cond, cmds + ["RELATIONS", "INFER ALL", "CONFLICTS", "ASK ? lives in ?"], f"fu3_s{seed}_d{int(dens*100)}")
            facts, conf, was, _ = read_session(out, w["preds"])
            g = collections.Counter(grade(current(facts, conf, "lives in", x), b) for x, a, b, e in evs)
            fl = sum(current(facts, conf, "lives in", x) is None for x in contra)
            rows.append({"seed": seed, "density": dens, "cond": cond, **{f"change_{k}": v for k, v in g.items()}, "contradictions_flagged": fl, "n_contra": len(contra)})
json.dump(rows, open("results_fu3.json", "w"), indent=1)
print(f"{'density':>7} {'cond':5} {'change right':>12} {'ambig':>6} {'contradictions flagged':>22}")
for dens in [0.05, 0.10, 0.15, 0.20]:
    for cond in ["A", "B", "C2", "C2fn"]:
        R = [r for r in rows if r["density"] == dens and r["cond"] == cond]
        n = sum(sum(v for k, v in r.items() if k.startswith("change_")) for r in R)
        print(f"{dens:7.2f} {cond:5} {sum(r.get('change_right', 0) for r in R) / n:12.2f} {sum(r.get('change_ambiguous', 0) for r in R) / n:6.2f} {sum(r['contradictions_flagged'] for r in R) / sum(r['n_contra'] for r in R):22.2f}")
