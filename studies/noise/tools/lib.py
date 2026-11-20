"""Harness for the noise study: generate a world, run the engine on the observation lines only, score against hidden truth.
The engine binary comes from the VOLTEX environment variable."""
import collections, json, os, subprocess, sys, tempfile, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "hidden"))
import gen  # noqa: E402

VOLTEX = os.environ.get("VOLTEX", os.path.join(HERE, "..", "..", "..", "build", "voltex2"))
OBS = os.path.join(HERE, "..", "obs")


def world(name, **kw):
    """Generate a world once and cache its observation file (obs/) and truth (hidden/cache/). Returns (obs_path, hidden)."""
    tag = name + "_" + "_".join(f"{k}{v}" for k, v in sorted(kw.items()))
    obs = os.path.join(OBS, tag + ".txt"); hid = os.path.join(HERE, "..", "hidden", "cache", tag + ".json")
    if not os.path.exists(obs) or not os.path.exists(hid):
        lines, h = gen.WORLDS[name](**kw)
        os.makedirs(OBS, exist_ok=True); os.makedirs(os.path.dirname(hid), exist_ok=True)
        with open(obs, "w") as f: f.write("\n".join(lines) + "\n")
        with open(hid, "w") as f: json.dump(h, f)
    with open(hid) as f: return obs, json.load(f)


def run(obs_path, settings=(), extra=""):
    """Run the engine on one observation file. settings: list of 'SET X v' lines."""
    cmds = "\n".join(list(settings) + [f"INGESTFILE {obs_path}", "RELATIONS", "INFER ALL", "CONFLICTS", extra, "EXIT"]) + "\n"
    return subprocess.run([VOLTEX], input=cmds, capture_output=True, text=True).stdout


def parse_fact(text, rels):
    for rel in rels:
        k = f" {rel} "
        if k in text:
            a, b = text.split(k, 1); return (rel, a.strip(), b.strip())
    return None


def facts_of(lines, rels):
    out = set()
    for l in lines:
        f = parse_fact(l, rels)
        if f: out.add(f)
    return out


def score(out, obs_path, hidden, with_causes=False, settings=()):
    rels = sorted(hidden["relations"], key=len, reverse=True)
    T = {tuple(x) for x in hidden["truth"]}
    stated = facts_of(open(obs_path).read().splitlines(), rels)
    corrupted = {(c[0], c[1], c[2]) for c in hidden["corrupted"]}
    derived = set()
    for l in out.splitlines():
        if l.startswith("FACT\t"):
            f = parse_fact(l.split("\t")[1], rels)
            if f: derived.add(f)
    new = derived - stated
    correct = new & T; wrong = new - T
    unseen = set(hidden.get("unseen", []))
    invented = {f for f in new if f[1] in unseen or f[2] in unseen}
    missing = {f for f in T - stated if f[1] not in unseen and f[2] not in unseen}
    flagged = set()
    for l in out.splitlines():
        if l.startswith("CONFLICT\t"):
            p = l.split("\t")   # CONFLICT <subject> <stated object> stated: <fact> | inferred: <fact> | because ...
            if len(p) >= 4 and "stated: " in p[3]:
                ft = p[3].split("stated: ", 1)[1].split(" | inferred:")[0]
                f = parse_fact(ft, rels)
                if f: flagged.add(f)
    r = {"stated": len(stated), "derived_new": len(new), "correct": len(correct), "wrong": len(wrong),
         "precision": len(correct) / len(new) if new else 1.0, "recall": len(correct & missing) / len(missing) if missing else 1.0,
         "invented_unseen": len(invented), "corrupted": len(corrupted & stated),
         "flagged": len(flagged), "flag_hits": len(flagged & corrupted),
         "rules_accepted": sum(1 for l in out.splitlines() if l.strip().startswith("ACCEPT")),
         "repl_rejected": sum(1 for l in out.splitlines() if "did not replicate" in l),
         "quarantined": sum(1 for l in out.splitlines() if l.startswith("CONFLICT\t") and "QUARANTINED" in l),
         "outvoted_stated": 0}
    # how many (relation, subject) pairs in the one-value relations have a wrong current stated value
    if with_causes and wrong:
        r.update(causes(obs_path, settings, wrong, corrupted, T, rels))
    return r


def causes(obs_path, settings, wrong, corrupted, T, rels):
    """Trace every wrong inference to its proof: 'propagation' if a premise (or a premise's premise) is a corrupted stated
    fact, 'rule' otherwise (the rule itself was wrong)."""
    asks = sorted({f"ASK {a} {rel} ?" for rel, a, b in wrong})
    out = run(obs_path, settings, "\n".join(asks))
    proof = {}
    for l in out.splitlines():
        if " inferred" in l and " because " in l and not l.startswith("FACT"):
            head = l.strip().split(" inferred")[0].strip()
            f = parse_fact(head, rels)
            if not f: continue
            body = l.split(" because ", 1)[1].split("  [rule:")[0]
            proof[f] = [parse_fact(p.strip(), rels) for p in body.split(" + ")]
    memo = {}

    def bad(f, depth=0):
        if f in memo: return memo[f]
        if f is None or depth > 12: return False
        if f in corrupted: memo[f] = True; return True
        memo[f] = False
        if f not in T and f in proof: memo[f] = any(bad(p, depth + 1) for p in proof[f])
        return memo[f]
    c = collections.Counter()
    for f in wrong:
        if f not in proof: c["cause_unknown"] += 1
        elif any(bad(p) for p in proof[f]): c["cause_propagation"] += 1
        else: c["cause_rule"] += 1
    return {k: c.get(k, 0) for k in ("cause_propagation", "cause_rule", "cause_unknown")}


def settings_lines(d):
    return [f"SET {k} {v}" for k, v in d.items()]
