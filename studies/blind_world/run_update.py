"""Capability E: the world changes after ingestion. Voltex is append-only, so corrections arrive as new statements.
Control: a fresh Voltex built from the corrected observations (what retraction would give)."""
import json, sys, random, collections, re
sys.path.insert(0, "hidden")
from world import generate, observe
from lib import Voltex, parse_fact

def run(seed, cov=0.5):
    T, E = generate(seed); lines, info = observe(T, E, seed, cov)
    obs = {tuple(f) for f in info["observed"]}
    rng = random.Random(seed + 500)
    loc = dict(map(tuple, T["is located in"])); lives = dict(map(tuple, T["lives in"]))
    observed_lives = sorted({(a, b) for p, a, b in obs if p == "lives in" and lives.get(a) == b})
    movers = rng.sample(observed_lives, 30)
    new_home = {}
    for a, s in movers:
        new_home[a] = rng.choice([x for x in E["settlement"] if loc[x] != loc[s]])
    moved_s = rng.choice(sorted({s for p, s, g in obs if p == "is located in" and loc.get(s) == g}))
    new_region = rng.choice([g for g in E["region"] if g != loc[moved_s]])
    updates = [f"{a} lives in {s}" for a, s in new_home.items()] + [f"{moved_s} is located in {new_region}", f"{new_region} contains {moved_s}"]
    loc2 = dict(loc); loc2[moved_s] = new_region
    lives2 = dict(lives); lives2.update(new_home)
    residents = sorted(a for a, s in observed_lives if s == moved_s and a not in new_home)
    def probe(vx, tag):
        res = collections.Counter(); detail = []
        def classify(q, new, old):
            ans = set()
            for l in vx.cmd(f"ASK {q}"):
                m = re.match(r"^\s+(.*?)\s+(stated|inferred)", l)
                if m:
                    f = parse_fact(m.group(1), ["is located in", "lives in", "is from"])
                    if f: ans.add(f[2])
            state = ("correct only" if ans == {new} else "new + stale" if new in ans and old in ans else
                     "stale only" if old in ans else "new + other" if new in ans else "no/other answer")
            return state, sorted(ans)
        for a, s in movers:
            st, ans = classify(f"{a} lives in ?", new_home[a], s); res["mover lives in: " + st] += 1
            st, ans = classify(f"{a} is from ?", loc[new_home[a]], loc[s]); res["mover is from: " + st] += 1; detail.append((a, ans))
        for a in residents:
            st, ans = classify(f"{a} is from ?", new_region, loc[moved_s]); res["resident of moved settlement, is from: " + st] += 1
        st, ans = classify(f"{moved_s} is located in ?", new_region, loc[moved_s]); res["moved settlement is located in: " + st] += 1
        return dict(sorted(res.items())), detail[:5]
    out = {"seed": seed, "movers": 30, "residents_of_moved_settlement": len(residents)}
    vx = Voltex(f"logs/update_s{seed}.log")
    open(f"obs/obs_update_base_s{seed}.txt", "w").write("\n".join(lines) + "\n")
    open(f"obs/obs_update_delta_s{seed}.txt", "w").write("\n".join(updates) + "\n")
    vx.cmd(f"INGESTFILE obs/obs_update_base_s{seed}.txt"); vx.cmd("RELATIONS"); vx.cmd("INFER")
    out["before_update"], _ = probe(vx, "before")
    vx.cmd(f"INGESTFILE obs/obs_update_delta_s{seed}.txt"); out["rules_after_update"] = vx.cmd("RELATIONS")[-0:]; vx.cmd("INFER")
    out["after_append_update"], out["examples"] = probe(vx, "after")
    out["conflicts_after_update"] = sum(1 for l in vx.cmd("CONFLICTS") if l.startswith("CONFLICT\t"))
    vx.close()
    # control: rebuild from corrected observations (old facts removed) -- what a retraction operation would allow
    fixed = [l for l in lines if not any(l == f"{a} lives in {s}" for a, s in movers)
             and l not in (f"{moved_s} is located in {loc[moved_s]}", f"{loc[moved_s]} contains {moved_s}")] + updates
    open(f"obs/obs_update_rebuilt_s{seed}.txt", "w").write("\n".join(fixed) + "\n")
    vx = Voltex(f"logs/update_rebuilt_s{seed}.log"); vx.cmd(f"INGESTFILE obs/obs_update_rebuilt_s{seed}.txt"); vx.cmd("RELATIONS"); vx.cmd("INFER")
    out["rebuilt_with_old_facts_removed"], _ = probe(vx, "rebuilt"); vx.close()
    out["rules_after_update"] = [l.strip()[:80] for l in out["rules_after_update"] if "ACCEPT" in l and "is from" in l]
    return out

res = [run(s) for s in range(5)]
json.dump(res, open("results/update_test.json", "w"), indent=1)
agg = collections.defaultdict(lambda: collections.Counter())
for r in res:
    for phase in ("before_update", "after_append_update", "rebuilt_with_old_facts_removed"):
        for k, v in r[phase].items(): agg[phase][k] += v
for phase, c in agg.items():
    print(f"\n{phase} (5 seeds, 150 movers):"); [print(f"   {k:58} {v}") for k, v in sorted(c.items())]
print("\nexample answers after append-only update:", res[0]["examples"][:3])
print("conflicts flagged after update:", [r["conflicts_after_update"] for r in res])
