"""Exp 2: updates. Same scenario as the blind-world test (30 movers + 1 relocated settlement, 5 seeds).
Protocols: A frozen append-only | B UPDATE for every new statement | C UPDATE single-value facts + RETRACT old multi-value fact.
Also: are the stale *stated* consequences ("X is from <old region>") flagged by CONFLICTS (distinct-rule corroboration)?"""
import json, random, collections, re, subprocess
from harness import *

def scenario(seed):
    w = world(seed, 0.5); T, E = w["T"], w["E"]; obs = set(w["observed"])
    rng = random.Random(seed + 500)
    loc = dict(map(tuple, T["is located in"])); lives = dict(map(tuple, T["lives in"]))
    observed_lives = sorted({(a, b) for p, a, b in obs if p == "lives in" and lives.get(a) == b})
    movers = rng.sample(observed_lives, 30)
    new_home = {a: rng.choice([x for x in E["settlement"] if loc[x] != loc[s]]) for a, s in movers}
    moved_s = rng.choice(sorted({s for p, s, g in obs if p == "is located in" and loc.get(s) == g}))
    new_region = rng.choice([g for g in E["region"] if g != loc[moved_s]])
    residents = sorted(a for a, s in observed_lives if s == moved_s and a not in new_home)
    stale_from = {(a, loc[s]) for a, s in movers if ("is from", a, loc[s]) in obs} | {(a, loc[moved_s]) for a in residents if ("is from", a, loc[moved_s]) in obs}
    return w, movers, new_home, moved_s, new_region, residents, loc, stale_from

def protocol_cmds(p, movers, new_home, moved_s, new_region, loc):
    if p.startswith("A"): return [f"INGEST {a} lives in {new_home[a]}" for a, _ in movers] + [f"INGEST {moved_s} is located in {new_region}", f"INGEST {new_region} contains {moved_s}"]
    if p.startswith("B"): return [f"UPDATE {a} lives in {new_home[a]}" for a, _ in movers] + [f"UPDATE {moved_s} is located in {new_region}", f"UPDATE {new_region} contains {moved_s}"]
    return [f"UPDATE {a} lives in {new_home[a]}" for a, _ in movers] + [f"UPDATE {moved_s} is located in {new_region}",
            f"RETRACT {loc[moved_s]} contains {moved_s}", f"INGEST {new_region} contains {moved_s}"]

agg = collections.defaultdict(collections.Counter); extra = collections.defaultdict(list)
for seed in range(5):
    w, movers, new_home, moved_s, new_region, residents, loc, stale_from = scenario(seed)
    for p in ["A append", "B UPDATE all", "C UPDATE+RETRACT", "D C + staleness check"]:
        binary = FROZEN if p.startswith("A") else EXP
        sets = [] if p.startswith("A") else ["SET COV 2", "SET TIERS 2"] + (["SET STALE 1"] if p.startswith("D") else [])
        qs = []
        for a, s in movers: qs += [f"ASK {a} lives in ?", f"ASK {a} is from ?"]
        for a in residents: qs.append(f"ASK {a} is from ?")
        qs.append(f"ASK {moved_s} is located in ?"); qs.append(f"ASK ? contains {moved_s}")
        cmds = sets + [f"INGESTFILE {w['path']}", "INFER"] + protocol_cmds(p, movers, new_home, moved_s, new_region, loc) + ["INFER"]
        marker = "FIND __q__"
        out = subprocess.run([binary], input="\n".join(cmds + [c for q in qs for c in (q, marker)] + ["CONFLICTS", "EXIT"]) + "\n", capture_output=True, text=True).stdout
        open(f"logs/exp2_{p.split()[0]}_s{seed}.log", "w").write(out)
        answers = out.split("[FIND] not stored\n")
        head, answers, tail = answers[0], answers[:-1], answers[-1]
        def objs(block, pred):
            res = set()
            for l in block.splitlines():
                m = re.match(r"^\s+(.*?)\s+(stated|inferred)", l)
                if m:
                    f = parse_fact(m.group(1), ["is located in", "lives in", "is from", "contains"])
                    if f: res.add(f[2] if pred != "contains" else f[1])
            return res
        def cls(ans, new, old):
            return "correct only" if ans == {new} else "new + stale" if {new, old} <= ans else "stale only" if old in ans else "new + other" if new in ans else "none/other"
        i = 0
        # the first block also contains the ingest/update output; ASK answers are the trailing lines of each block
        for a, s in movers:
            agg[p]["mover lives in: " + cls(objs(answers[i], "lives in"), new_home[a], s)] += 1; i += 1
            agg[p]["mover is from: " + cls(objs(answers[i], "is from"), loc[new_home[a]], loc[s])] += 1; i += 1
        for a in residents:
            agg[p]["resident is from: " + cls(objs(answers[i], "is from"), new_region, loc[moved_s])] += 1; i += 1
        agg[p]["settlement located in: " + cls(objs(answers[i], "is located in"), new_region, loc[moved_s])] += 1; i += 1
        agg[p]["region contains settlement: " + cls(objs(answers[i], "contains"), new_region, loc[moved_s])] += 1; i += 1
        flagged = {(l.split("\t")[1], l.split("\t")[2]) for l in tail.splitlines() if l.startswith("CONFLICT\t")}
        extra[p].append((len(stale_from), len(flagged & stale_from), len(flagged)))
        agg[p]["UPDATE replaced"] += sum(int(m) for m in re.findall(r"replaced (\d+) earlier", out))
for p, c in agg.items():
    print(f"\n{p}:")
    for k, v in sorted(c.items()): print(f"   {k:46} {v}")
    st_, hit, fl = (sum(x[i] for x in extra[p]) for i in range(3))
    print(f"   stale stated 'is from' facts: {st_} | flagged by CONFLICTS: {hit} | total flags: {fl}")
json.dump({k: dict(v) for k, v in agg.items()}, open("results_exp2_update.json", "w"), indent=1)
