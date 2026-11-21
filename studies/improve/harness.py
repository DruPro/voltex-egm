"""Shared harness for the improvement experiments. Runs frozen or experimental Voltex with switches; scores with the hidden evaluator."""
import sys, os, json, random, re, subprocess, collections
W = "/home/claude/work"
sys.path.insert(0, f"{W}/blind/hidden"); sys.path.insert(0, f"{W}/blind")
from world import generate, observe
from evaluate import evaluate, rule_true_confidence
from lib import parse_rules, parse_fact, oracle
FROZEN, EXP = f"{W}/blind/frozen/voltex2", f"{W}/improve/voltex2_exp"
DATA = f"{W}/improve/data"; os.makedirs(DATA, exist_ok=True); os.makedirs(f"{W}/improve/logs", exist_ok=True)

def observe_nonuniform(T, E, seed, lo=0.2, hi=0.9):
    """Like observe(), but every predicate gets its own coverage in [lo, hi] -- real data is not missing at random."""
    rng = random.Random(seed + 4242)
    cov = {p: round(rng.uniform(lo, hi), 2) for p in sorted(T)}
    lines_all, info = observe(T, E, seed, 1.0)              # full observation with the usual noise / unseen / sparse
    obs = [tuple(f) for f in info["observed"]]
    keep = [f for f in obs if f[1] in info["sparse"] or rng.random() < cov[f[0]] or any(w[1] == f[1] and w[2] == f[2] for w in info["wrong"])]
    info["observed"] = [list(f) for f in keep]
    lines = [f"{a} {p} {b}" for p, a, b in keep]; rng.shuffle(lines)
    return lines, info, cov

def run(binary, obs_file, sets=(), extra_cmds=(), log=None):
    cmds = [f"SET {s}" for s in sets] + [f"INGESTFILE {obs_file}", "RELATIONS", "INFER ALL", "CONFLICTS"] + list(extra_cmds) + ["EXIT"]
    out = subprocess.run([binary], input="\n".join(cmds) + "\n", capture_output=True, text=True).stdout
    if log: open(log, "w").write(out)
    return out

def parse_out(out, preds):
    lines = out.splitlines()
    rules = parse_rules(lines)
    for l, r in zip([l for l in lines if re.match(r"\s+(ACCEPT|reject) \[", l)], rules):
        m = re.search(r"cov=([-\d.]+) rel=([\d.]+) tier=(\w+)", l)
        if m: r["cov"], r["rel"], r["tier"] = float(m.group(1)), float(m.group(2)), m.group(3)
    derived, tiers = set(), {}
    for l in lines:
        if l.startswith("FACT\t"):
            parts = l.split("\t"); f = parse_fact(parts[1], preds)
            if f: derived.add(f); tiers[f] = parts[2] if len(parts) > 2 else None
    conflicts = [tuple(l.split("\t")[1:4]) for l in lines if l.startswith("CONFLICT\t")]
    cov = {}
    for l in lines:
        if l.startswith("[COVERAGE]"):
            cov["global"] = float(re.search(r"global ([-\d.]+)", l).group(1))
            for m in re.finditer(r"\[\? (.*?) \?\] ([\d.]+)", l): cov[m.group(1)] = float(m.group(2))
    return rules, derived, tiers, conflicts, cov

def world(seed, cov=None, nonuniform=False, scale=1):
    T, E = generate(seed, scale)
    if nonuniform: lines, info, pc = observe_nonuniform(T, E, seed)
    else: lines, info = observe(T, E, seed, cov); pc = {p: cov for p in T}
    tag = f"s{seed}_" + ("nu" if nonuniform else f"c{int(cov * 100)}")
    path = f"{DATA}/obs_{tag}.txt"; open(path, "w").write("\n".join(lines) + "\n")
    preds = sorted(T, key=len, reverse=True)
    observed = [tuple(f) for f in info["observed"]]
    return {"T": T, "E": E, "info": info, "path": path, "preds": preds, "observed": observed, "tag": tag, "true_cov": pc,
            "oracle": oracle(observed)}

def true_observed_rate(w):
    """Actual fraction of each predicate's true facts that were observed (excluding withheld entities)."""
    obs = set(w["observed"]); out = {}
    hidden = set(w["info"]["unseen"]) | set(w["info"]["sparse"])
    for p, fs in w["T"].items():
        fs = [tuple(f) for f in fs if f[0] not in hidden and f[1] not in hidden]
        if fs: out[p] = sum((p, a, b) in obs for a, b in fs) / len(fs)
    return out
