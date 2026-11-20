"""Amendments experiment (see PREREGISTRATION.md). Usage: python3 exp_amend.py [seeds] [rates]"""
import sys, os, re, json, random, time, subprocess, collections
sys.path.insert(0, "/home/claude/work/improve")
from harness import world, parse_rules, parse_fact
sys.path.insert(0, "/home/claude/work/blind/hidden")
from world import EXPRESSIBLE_TRUE_RULES, DECOY_RULES

W = "/home/claude/work"
V21, AM = f"{W}/v21/voltex2", f"{W}/amend/voltex2_amend"
OUT = f"{W}/amend"; os.makedirs(f"{OUT}/logs", exist_ok=True); os.makedirs(f"{OUT}/data", exist_ok=True)
VARIANTS = {"V0_update": (V21, "UPDATE", []),
            "V1_history": (AM, "AMEND", ["SET EXPLAIN 0", "SET DEPEV 0", "SET SUSPECT 0"]),
            "V2_explain": (AM, "AMEND", ["SET EXPLAIN 1", "SET DEPEV 0", "SET SUSPECT 0"]),
            "V3_explain_depev": (AM, "AMEND", ["SET EXPLAIN 1", "SET DEPEV 1", "SET SUSPECT 0"]),
            "V2b_samerule": (AM, "AMEND", ["SET EXPLAIN 2", "SET DEPEV 0", "SET SUSPECT 0"])}

def make_moves(w, seed, rate):
    T, E, info = w["T"], w["E"], w["info"]
    region = dict(map(tuple, T["is located in"]))
    true_lives = dict(map(tuple, T["lives in"]))
    obs = set(w["observed"])
    wrong_subj = {x[1] for x in info["wrong"]}
    cands = sorted(a for (p, a, b) in obs if p == "lives in" and true_lives.get(a) == b and a not in wrong_subj and a not in info["sparse"])
    rng = random.Random(seed * 31 + int(rate * 1000))
    movers = rng.sample(cands, max(1, round(rate * len(cands))))
    moves = {}
    for p in movers:
        old = true_lives[p]
        new = rng.choice([s for s in E["settlement"] if region[s] != region[old]])
        moves[p] = (old, new)
    return moves, region, true_lives

def run_variant(name, w, moves, tag):
    binary, verb, sets = VARIANTS[name]
    cmds = sets + [f"INGESTFILE {w['path']}"] + [f"{verb} {p} lives in {new}" for p, (old, new) in sorted(moves.items())]
    cmds += ["RELATIONS", "INFER ALL", "CONFLICTS"]
    if verb == "AMEND":
        for p in sorted(moves): cmds.append(f"HISTORY {p}")
    cmds.append("EXIT")
    t0 = time.time()
    out = subprocess.run([binary], input="\n".join(cmds) + "\n", capture_output=True, text=True).stdout
    dt = time.time() - t0
    open(f"{OUT}/{os.environ.get("LOGDIR","logs")}/{name}_{tag}.log", "w").write(out)
    return out, dt

def parse(out, preds):
    lines = out.splitlines()
    rules = parse_rules(lines)
    derived = set()
    for l in lines:
        if l.startswith("FACT\t"):
            f = parse_fact(l.split("\t")[1], preds)
            if f: derived.add(f)
    conflicts = {}
    for l in lines:
        if l.startswith("CONFLICT\t"):
            m = re.search(r"stated: (.*?) \| inferred: (.*?) \| because (.*)", l)
            s, i = parse_fact(m.group(1), preds), parse_fact(m.group(2), preds)
            if s and i: conflicts[(s[0], s[1])] = (None if i[2] == s[2] else i[2], "STALE: it followed from" in m.group(3), "POSSIBLY STALE" in m.group(3))
    hist = {}
    cur = None
    for l in lines:
        m = re.match(r"\s+#\d+ (changed|corrected): '(.*?)' -> '(.*?)'", l)
        if m:
            o = parse_fact(m.group(2), preds)
            if o: hist[o[1]] = o[2]
    return rules, derived, conflicts, hist

def norm_rule(r):
    f = lambda x: re.sub(r"\?\s*|\s*\?", "", x).strip() if x else None
    return (r["type"], f(r["r1"]), f(r["r2"]) if r["type"] != "I" else None, f(r["r3"]))

def score(w, moves, region, true_lives, rules, derived, conflicts, hist):
    obs = set(w["observed"])
    stated_from = {a: b for (p, a, b) in obs if p == "is from"}
    stated_lives = {a: b for (p, a, b) in obs if p == "lives in"}
    true_from = dict(map(tuple, w["T"]["is from"]))
    derived_from = {a: b for (p, a, b) in derived if p == "is from"}
    def answer(pred, a, stated):
        if (pred, a) in conflicts: return conflicts[(pred, a)][0]
        return stated
    cur_region = {p: region[new] for p, (old, new) in moves.items()}
    stale = [p for p in moves if stated_from.get(p) == true_from.get(p)]          # stated old region, now stale
    m2 = sum(answer("is from", p, stated_from[p]) == cur_region[p] for p in stale)
    abst = sum(answer("is from", p, stated_from[p]) is None for p in stale)
    wrong = len(stale) - m2 - abst
    known_loc = {a for (p_, a, b) in obs if p_ == "is located in"} | {b for (p_, a, b) in obs if p_ == "contains"}
    deriv = [p for p in stale if moves[p][1] in known_loc]
    m2d = sum(answer("is from", p, stated_from[p]) == cur_region[p] for p in deriv)
    noflag = [p for p in moves if p not in stated_from]
    m2b = sum(derived_from.get(p) == cur_region[p] for p in noflag)
    nonmov = [a for a in stated_from if a not in moves and stated_from[a] == true_from.get(a)]
    m3 = sum(answer("is from", a, stated_from[a]) == true_from[a] for a in nonmov)
    nonmov_l = [a for a in stated_lives if a not in moves and stated_lives[a] == true_lives.get(a)]
    m3b = sum(answer("lives in", a, stated_lives[a]) == true_lives[a] for a in nonmov_l)
    m1 = sum(answer("lives in", p, new) == new for p, (old, new) in moves.items())
    m5 = sum(hist.get(p) == old for p, (old, new) in moves.items())
    acc = {norm_rule(r) for r in rules if r["accepted"]}
    true_r = {(t, a, b if t != "I" else None, c) for t, a, b, c in EXPRESSIBLE_TRUE_RULES}
    decoy_r = {(t, a, b, c) for t, a, b, c in DECOY_RULES}
    law = 0
    return {"movers": len(moves), "stale_stated": len(stale), "M1": m1 / len(moves), "M2": m2 / len(stale) if stale else None,
            "M2_wrong": wrong / len(stale) if stale else None, "M2_abstain": abst / len(stale) if stale else None,
            "M2_derivable": m2d / len(deriv) if deriv else None, "n_derivable": len(deriv), "M2b_derived_only": m2b / len(noflag) if noflag else None, "M3": m3 / len(nonmov), "M3b": m3b / len(nonmov_l),
            "M5": m5 / len(moves), "true_rules": len(acc & true_r), "decoys": len(acc & decoy_r),
            "stale_flags": sum(1 for v in conflicts.values() if v[1]), "possibly_stale_flags": sum(1 for v in conflicts.values() if v[2]),
            "_acc": sorted(map(str, acc))}

def law_true_rules(out):
    n = 0
    for l in out.splitlines():
        if re.match(r"\s+ACCEPT \[", l) and "tier=law" in l: n += 1
    return n

if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1, 2, 3, 4, 5]
    rates = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [0.01, 0.05, 0.15, 0.30]
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else list(VARIANTS)
    rows = []
    resf = os.environ.get("RESULTS", f"{OUT}/results_amend.json")
    if os.path.exists(resf): rows = [r for r in json.load(open(resf)) if not (r["seed"] in seeds and r["rate"] in rates and r["variant"] in names)]
    for seed in seeds:
        w = world(seed, 0.5)
        for rate in rates:
            moves, region, true_lives = make_moves(w, seed, rate)
            tag = f"s{seed}_m{int(rate * 100)}"
            for name in names:
                out, dt = run_variant(name, w, moves, tag)
                rules, derived, conflicts, hist = parse(out, w["preds"])
                r = score(w, moves, region, true_lives, rules, derived, conflicts, hist)
                r.update({"seed": seed, "rate": rate, "variant": name, "seconds": round(dt, 2), "law_rules_accepted": law_true_rules(out),
                          "facts_derived": len(derived)})
                rows.append(r)
                print(f"s{seed} m{rate:.2f} {name:18} M1={r['M1']:.3f} M2={r['M2']} wrong={r['M2_wrong']} abst={r['M2_abstain']} M3={r['M3']:.4f} M3b={r['M3b']:.4f} M5={r['M5']:.2f} "
                      f"rules={r['true_rules']} law={r['law_rules_accepted']} decoys={r['decoys']} stale={r['stale_flags']} pstale={r['possibly_stale_flags']} t={dt:.1f}s", flush=True)
                json.dump(rows, open(resf, "w"), indent=1)
