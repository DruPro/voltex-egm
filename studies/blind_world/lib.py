"""Runners for the four systems. Only `Voltex` touches the frozen binary, and it only sees observation files."""
import subprocess, time, re, collections, os, random

BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frozen", "voltex2")

class Voltex:
    """Drives the frozen, unmodified binary through its normal command interface; logs everything."""
    def __init__(self, log_path):
        self.p = subprocess.Popen(["stdbuf", "-oL", BIN], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.log = open(log_path, "w"); self.timings = collections.defaultdict(list)
    def cmd(self, line, quiet=False):
        t = time.perf_counter()
        self.p.stdin.write(line + "\nFIND __end_marker__\n"); self.p.stdin.flush()
        out = []
        while True:
            l = self.p.stdout.readline()
            if not l or l.startswith("[FIND] not stored"): break
            out.append(l.rstrip("\n"))
        dt = time.perf_counter() - t
        self.timings[line.split()[0]].append(dt)
        if not quiet or len(out) < 50: self.log.write(f"voltex2# {line}\n" + "\n".join(out) + f"\n[elapsed {dt * 1000:.2f} ms]\n")
        else: self.log.write(f"voltex2# {line}\n" + "\n".join(out) + f"\n[elapsed {dt * 1000:.2f} ms]\n")
        return out
    def close(self):
        self.p.stdin.write("EXIT\n"); self.p.stdin.flush(); self.p.wait(); self.log.close()

RULE_RE = re.compile(r"\s+(ACCEPT|reject) \[\? (.*?) \?\]\(a,b\)(?: & \[\? (.*?) \?\]\(b,c\))? => \[\? (.*?) \?\]\((b,a|a,c)\)\s+n=(\d+) k=(\d+) rate=([\d.]+) lift=([\d.]+) \| where answer known: (\d+), agree=([\d.]+)")
def parse_rules(lines):
    out = []
    for l in lines:
        m = RULE_RE.match(l)
        if not m: continue
        acc, r1, r2, r3, d, n, k, rate, lift, pn, agree = m.groups()
        typ = "I" if d == "b,a" else ("T" if r1 == r2 == r3 else "C")
        out.append({"accepted": acc == "ACCEPT", "type": typ, "r1": r1, "r2": r2, "r3": r3, "n": int(n), "k": int(k),
                    "rate": float(rate), "lift": float(lift), "known": int(pn), "agree": float(agree)})
    return out

def parse_fact(text, preds):
    for p in preds:                                  # longest predicate phrase first
        sep = f" {p} "
        if sep in f" {text} ":
            a, b = text.split(f" {p} ", 1)
            if a and b and " " not in a.strip() and " " not in b.strip(): return (p, a.strip(), b.strip())
    return None

def run_voltex(obs_file, log_path, preds, rules_on=True, n_queries=200, seed=0, extra=None):
    vx = Voltex(log_path); res = {}
    if not rules_on: vx.cmd("SET SUPPORT 1000000000")
    ing = vx.cmd(f"INGESTFILE {obs_file}")
    res["ingest_line"] = ing[0] if ing else ""
    rel = vx.cmd("RELATIONS")
    res["rules"] = parse_rules(rel); res["templates"] = [l.strip() for l in rel if l.strip().startswith("#")]
    inf = vx.cmd("INFER ALL", quiet=True)
    res["derived"] = set(filter(None, (parse_fact(l.split("\t")[1], preds) for l in inf if l.startswith("FACT\t"))))
    res["unparsed_derived"] = sum(1 for l in inf if l.startswith("FACT\t") and not parse_fact(l.split("\t")[1], preds))
    conf = vx.cmd("CONFLICTS")
    res["conflicts"] = [tuple(l.split("\t")[1:4]) for l in conf if l.startswith("CONFLICT\t")]
    met = vx.cmd("METRICS")
    res["rss_mb"] = float(next((l.split(":")[1].split()[0] for l in met if "RSS" in l), "nan"))
    # query latency: ASK on random subjects of random predicates
    rng = random.Random(seed); subj = sorted({f[1] for f in res["derived"]}) or ["x"]
    for _ in range(n_queries): vx.cmd(f"ASK {rng.choice(subj)} {rng.choice(preds)} ?")
    if extra: res["extra"] = extra(vx)
    t = vx.timings
    res["latency_ms"] = {"ingest": t["INGESTFILE"][0] * 1000, "model_build(classes+relations+rule mining)": t["RELATIONS"][0] * 1000,
                         "infer_all": t["INFER"][0] * 1000, "ask_mean": 1000 * sum(t["ASK"]) / max(1, len(t["ASK"])),
                         "ask_p95": 1000 * sorted(t["ASK"])[int(0.95 * len(t["ASK"])) - 1] if t["ASK"] else 0}
    vx.close()
    return res

# ---------------- baselines ----------------
def graph_baseline(observed, preds):
    """Naive link prediction: predict p(a,c) when c is within 2 hops of a (labels ignored),
    a looks like a subject of p, and c is an observed object of p."""
    adj = collections.defaultdict(set); subj_kind = collections.Counter(); kind_votes = collections.defaultdict(collections.Counter)
    by_pred = collections.defaultdict(set)
    for p, a, b in observed:
        adj[a].add(b); adj[b].add(a); by_pred[p].add((a, b)); kind_votes[a][p] += 1
    kind = {e: c.most_common(1)[0][0] for e, c in kind_votes.items()}
    derived = set()
    for p in preds:
        subs = {a for a, _ in by_pred[p]}; rng_ = {b for _, b in by_pred[p]}
        kinds = collections.Counter(kind[a] for a in subs)
        if not kinds: continue
        k0 = kinds.most_common(1)[0][0]
        for a in [e for e, k in kind.items() if k == k0]:
            two = set(adj[a])
            for x in list(adj[a]): two |= adj[x]
            for c in (two & rng_) - {a}:
                if (a, c) not in by_pred[p]: derived.add((p, a, c))
    return derived

def oracle(observed, overseen_known=True):
    """Upper-bound reference: forward chaining with the TRUE rules (written by hand from the generator).
    Returns {fact: depth} for derived facts not in the observations."""
    facts = {f: 0 for f in observed}
    def rel(p): return {(a, b) for (q, a, b) in facts if q == p}
    depth = 0
    while True:
        depth += 1; new = {}
        R = {p: rel(p) for p in ["lives in", "is located in", "contains", "is parent of", "is child of", "is sibling of",
                                  "borders", "is ancestor of", "produces", "works as", "is overseen by"]}
        out = lambda p: _index(R[p])
        def add(f):
            if f not in facts and f not in new: new[f] = depth
        for a, s in R["lives in"]:
            for g in out("is located in").get(s, ()): add(("is from", a, g))
        for a, b in R["is located in"]: add(("contains", b, a))
        for a, b in R["contains"]: add(("is located in", b, a))
        for a, b in R["is parent of"]: add(("is child of", b, a)); add(("is ancestor of", a, b))
        for a, b in R["is child of"]: add(("is parent of", b, a))
        for a, b in R["is sibling of"]: add(("is sibling of", b, a))
        for a, b in R["borders"]: add(("borders", b, a))
        anc = out("is ancestor of")
        for a, b in R["is ancestor of"]:
            for c in anc.get(b, ()): add(("is ancestor of", a, c))
        par = out("is parent of")
        for a, p in R["is child of"]:
            for c in par.get(p, ()):
                if c != a: add(("is sibling of", a, c))
        prod = out("produces")
        for g, s in R["contains"]:
            for r in prod.get(s, ()): add(("exports", g, r))
        ov = out("is overseen by")
        for a, f in R["works as"]:
            for i in ov.get(f, ()): add(("is member of", a, i))
            if f in ("farmer", "miner"):
                for s in out("lives in").get(a, ()):
                    for r in prod.get(s, ()): add(("harvests", a, r))
        if not new: break
        facts.update(new)
    return {f: d for f, d in facts.items() if d > 0}

def _index(pairs):
    d = collections.defaultdict(set)
    for a, b in pairs: d[a].add(b)
    return d
