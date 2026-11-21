"""Sharding as an external layer: split a facts file into shards, run one unchanged engine per shard, union the answers.

This module sees only the facts file. It never reads an answer key.

Facts are lines `subject relation words object` with one-word names (docs/DATA_DESIGN.md), so the subject is the
first word, the object the last, and the relation everything between.

Two steps:

1. **Assignment** gives some entities a shard ("members"). Everything else is reference data.
   - boundary="key":        each subject of the key relation goes to the shard of its key object (majority of its
                            stated key objects, ties to the smallest name). Key objects are dealt round-robin in name
                            order. This is the scale study's split (key = "is on"), which noise in the key corrupts.
   - boundary="components": connected components of the graph formed by the `graph` relations are packed into shards
                            (largest first, onto the least-loaded shard). Then one attach pass: an unassigned entity
                            joins a shard if every assigned neighbour through the `attach` relations is in that shard.
2. **Routing.** A fact goes to the shard of its subject, else of its object. A fact with neither endpoint assigned is a
   reference fact. A reference fact goes to every shard that mentions its subject; routing it makes its object
   mentioned too, repeated to a fixed point (subject direction only, so a city does not pull in every team in it).

central=True adds a central stage: one engine learns from all reference facts; its law-tier conclusions are added
to the reference facts before routing (the two-stage gate of docs/DATA_DESIGN.md 5.1), and its answers join the union.
"""
import collections, os, resource, subprocess, threading, time

COMMANDS = ["RELATIONS", "INFER ALL", "CONFLICTS"]


def split_fact(line):
    w = line.split()
    if len(w) < 3: return None
    return w[0], " ".join(w[1:-1]), w[-1]


def words_in(lines):
    return len({x for l in lines for x in l.split()})


def maxwords_for(lines):
    """The cap rule of this study: the default 12000, or the input's vocabulary plus 1000 if larger."""
    return max(12000, words_in(lines) + 1000)


def run_engine(binary, facts_path, settings, rss_limit_kb=None, extra=()):
    """Run one engine. Returns (stdout, stats) with seconds (wall), cpu (user+sys) and peak RSS in MB from wait4.
    rss_limit_kb: kill the process if its resident memory passes this (stats["killed"] = True)."""
    cmds = "\n".join([f"SET {k} {v}" for k, v in settings.items()] + [f"INGESTFILE {facts_path}"] + COMMANDS + list(extra) + ["EXIT"]) + "\n"
    t = time.time()
    p = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    killed = [False]

    def watch():
        while p.poll() is None:
            try:
                for l in open(f"/proc/{p.pid}/status"):
                    if l.startswith("VmRSS:") and int(l.split()[1]) > rss_limit_kb: killed[0] = True; p.kill()
            except OSError:
                return
            time.sleep(0.2)
    if rss_limit_kb: threading.Thread(target=watch, daemon=True).start()
    def feed():                                   # write in a thread: a long ASK list would otherwise fill the pipe
        p.stdin.write(cmds); p.stdin.close()      # while the engine blocks writing output nobody reads yet
    w = threading.Thread(target=feed, daemon=True); w.start()
    out = p.stdout.read(); w.join()
    _, status, ru = os.wait4(p.pid, 0)
    p.returncode = os.waitstatus_to_exitcode(status)
    return out, {"seconds": round(time.time() - t, 3), "cpu": round(ru.ru_utime + ru.ru_stime, 3),
                 "rss_mb": round(ru.ru_maxrss / 1024, 1), "exit": p.returncode, "killed": killed[0],
                 "limit_lines": [l for l in out.splitlines() if l.startswith("[LIMIT]")]}


def facts_out(out):
    """(fact, tier) for every FACT line."""
    r = []
    for l in out.splitlines():
        if l.startswith("FACT\t"):
            p = l.split("\t"); r.append((p[1], p[2] if len(p) > 2 else ""))
    return r


def accepted_rules(out):
    """Rule texts of the ACCEPT lines printed by RELATIONS."""
    return {l.strip()[len("ACCEPT "):].split(" n=")[0].strip() for l in out.splitlines() if l.strip().startswith("ACCEPT ")}


def proofs(out):
    """{fact: (rule, [premise facts])} from ASK lines for inferred answers."""
    r = {}
    for l in out.splitlines():
        if " inferred" not in l or " because " not in l or "[rule: " not in l or l.startswith("FACT"): continue
        head = l.strip().split(" inferred")[0].strip()
        body, rule = l.split(" because ", 1)[1].split("  [rule: ", 1)
        r[" ".join(head.split())] = (rule.rsplit("]", 1)[0].strip(), [" ".join(x.split()) for x in body.split(" + ")])
    return r


def asks_for(facts):
    """One ASK per (subject, relation) among derived facts."""
    return sorted({f"ASK {f[0]} {f[1]} ?" for f in map(split_fact, facts) if f})


def assign(lines, n, boundary, key=None, graph=(), attach=()):
    parsed = [split_fact(l) for l in lines]
    shard_of = {}
    if boundary == "key":
        objs = sorted({f[2] for f in parsed if f and f[1] == key})
        home = {o: i % n for i, o in enumerate(objs)}
        votes = collections.defaultdict(collections.Counter)
        for f in parsed:
            if f and f[1] == key: votes[f[0]][f[2]] += 1
        for s, c in votes.items():
            best = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            shard_of[s] = home[best]
    elif boundary == "components":
        adj = collections.defaultdict(set)
        for f in parsed:
            if f and f[1] in graph: adj[f[0]].add(f[2]); adj[f[2]].add(f[0])
        seen, comps = set(), []
        for v in sorted(adj):
            if v in seen: continue
            comp, stack = [], [v]; seen.add(v)
            while stack:
                x = stack.pop(); comp.append(x)
                for y in adj[x]:
                    if y not in seen: seen.add(y); stack.append(y)
            comps.append(sorted(comp))
        comps.sort(key=lambda c: (-len(c), c[0]))
        load = [0] * n
        for c in comps:
            i = min(range(n), key=lambda j: (load[j], j)); load[i] += len(c)
            for x in c: shard_of[x] = i
        nb = collections.defaultdict(set)
        for f in parsed:
            if f and f[1] in attach: nb[f[0]].add(f[2]); nb[f[2]].add(f[0])
        add = {}
        for v in sorted(nb):
            if v in shard_of: continue
            homes = {shard_of[y] for y in nb[v] if y in shard_of}
            if len(homes) == 1: add[v] = homes.pop()
        shard_of.update(add)                     # one pass: attached entities do not attach others
    else:
        raise ValueError(boundary)
    return shard_of


def route(lines, n, shard_of, extra_reference=()):
    """Returns (shard line lists in input order, reference line list). extra_reference are routed like reference facts
    and placed after the shard's own lines."""
    own = [[] for _ in range(n)]
    ref_idx = []
    for i, l in enumerate(lines):
        f = split_fact(l)
        if not f: continue
        s = shard_of.get(f[0], shard_of.get(f[2]))
        if s is None: ref_idx.append(i)
        else: own[s].append(i)
    ref_lines = [lines[i] for i in ref_idx] + list(extra_reference)
    by_subject = collections.defaultdict(list)
    for j, l in enumerate(ref_lines): by_subject[split_fact(l)[0]].append(j)
    shards = []
    for s in range(n):
        mentioned = set()
        for i in own[s]:
            f = split_fact(lines[i]); mentioned.add(f[0]); mentioned.add(f[2])
        taken, frontier = set(), list(mentioned)
        while frontier:
            e = frontier.pop()
            for j in by_subject.get(e, ()):
                if j in taken: continue
                taken.add(j); o = split_fact(ref_lines[j])[2]
                if o not in mentioned: mentioned.add(o); frontier.append(o)
        # keep the input order: own lines and stated reference lines by input position, then extra reference lines
        pos = set(own[s]) | {ref_idx[j] for j in taken if j < len(ref_idx)}
        shards.append([lines[i] for i in sorted(pos)] + [ref_lines[j] for j in sorted(taken) if j >= len(ref_idx)])
    return shards, ref_lines


def shard_run(facts_path, workdir, binary, n, boundary, central=False, consensus=False, settings=None, **bkw):
    """Run the whole sharded pipeline. Returns (answers {fact: tier}, report).
    consensus=True keeps a shard's answer only if the rule behind it was accepted in a strict majority of shards and
    every derived premise of its proof is kept too. This needs each answer's proof: one ASK per derived
    (subject, relation), in a second engine session per shard (INFER ALL prints no rules)."""
    settings = dict(settings or {})
    lines = [l for l in open(facts_path).read().splitlines() if l.strip()]
    os.makedirs(workdir, exist_ok=True)
    shard_of = assign(lines, n, boundary, **bkw)
    report = {"n": n, "boundary": boundary, "central": central, "assigned": len(shard_of), "engines": []}
    answers = {}
    extra = []
    if central:
        _, ref = route(lines, n, shard_of)
        p = os.path.join(workdir, "central.txt")
        open(p, "w").write("\n".join(ref) + "\n")
        out, st = run_engine(binary, p, {"MAXWORDS": maxwords_for(ref), **settings})
        open(os.path.join(workdir, "central.out"), "w").write(out)
        fo = facts_out(out)
        extra = [f for f, t in fo if t == "law"]
        for f, t in fo: answers.setdefault(f, t)
        report["engines"].append({"name": "central", "facts": len(ref), "law_passed": len(extra), **st})
    shards, ref = route(lines, n, shard_of, extra)
    covered = set()
    for sl in shards: covered.update(sl)
    report["reference_facts"] = len(ref) - len(extra)
    # input lines no shard sees; with a central stage they are still seen by the central engine
    report["unrouted_lines"] = sum(1 for l in lines if l not in covered)
    seen_by_central = set(ref) if central else set()
    report["unseen_lines"] = sum(1 for l in lines if l not in covered and l not in seen_by_central)
    per_shard = []
    for s, sl in enumerate(shards):
        p = os.path.join(workdir, f"shard{s:02d}.txt")
        open(p, "w").write("\n".join(sl) + "\n")
        out, st = run_engine(binary, p, {"MAXWORDS": maxwords_for(sl), **settings})
        open(os.path.join(workdir, f"shard{s:02d}.out"), "w").write(out)
        fo = facts_out(out)
        if consensus:
            out2, st2 = run_engine(binary, p, {"MAXWORDS": maxwords_for(sl), **settings}, extra=asks_for(f for f, _ in fo))
            for k in ("seconds", "cpu"): st[k] = round(st[k] + st2[k], 3)
            st["rss_mb"] = max(st["rss_mb"], st2["rss_mb"]); st["exit"] = st["exit"] or st2["exit"]
            per_shard.append((fo, accepted_rules(out), proofs(out2)))
        else:
            for f, t in fo:
                if answers.get(f) != "law": answers[f] = t
        report["engines"].append({"name": f"shard{s:02d}", "facts": len(sl), **st})
    if consensus:
        votes = collections.Counter(r for _, acc, _ in per_shard for r in acc)
        majority = {r for r, c in votes.items() if c > n / 2}
        dropped = missing_proof = 0
        for fo, _, pr in per_shard:
            derived = {f for f, _ in fo}; memo = {}

            def keep(f, depth=0):
                if f in memo: return memo[f]
                memo[f] = False                     # cycle guard
                if f not in pr or depth > 50: return False
                rule, prem = pr[f]
                memo[f] = rule in majority and all(keep(x, depth + 1) for x in prem if x in derived)
                return memo[f]
            for f, t in fo:
                if f not in pr: missing_proof += 1
                if keep(f):
                    if answers.get(f) != "law": answers[f] = t
                else: dropped += 1
        report.update(rules_minority=sorted(r for r in votes if r not in majority), dropped=dropped,
                      missing_proof=missing_proof)
    E = report["engines"]
    report.update(cpu=round(sum(e["cpu"] for e in E), 3), seconds=round(sum(e["seconds"] for e in E), 3),
                  rss_mb=max(e["rss_mb"] for e in E), limit_lines=sum(len(e["limit_lines"]) for e in E),
                  failed=sum(1 for e in E if e["exit"] != 0 or e["killed"]))
    return answers, report
