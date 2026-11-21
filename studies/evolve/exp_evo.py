"""Dynamic relational evolution study (PREREGISTRATION.md).
Worlds: people (blind world), database, code. Conditions: A, B, C, D, Dx, P. Usage: python3 exp_evo.py [seeds] [conditions] [worlds]"""
import sys, os, re, json, random, time, subprocess, statistics as st, collections, itertools
sys.path.insert(0, "/home/claude/work/improve")
from harness import world as blind_world, parse_rules
sys.path.insert(0, "/home/claude/work/blind/hidden")
from world import EXPRESSIBLE_TRUE_RULES, DECOY_RULES

W = "/home/claude/work"; E = f"{W}/evolve"
BIN = {"A": f"{W}/v21/voltex2", "B": f"{W}/amend/voltex2_amend", "C": f"{W}/v21/voltex2", "D": f"{E}/voltex2_evo", "Dx": f"{E}/voltex2_evo",
       "P": f"{W}/declarative/voltex2_decl"}
PRE = {"A": [], "B": ["SET EXPLAIN 2", "SET DEPEV 0", "SET SUSPECT 0"], "C": [], "D": ["SET DX 0"], "Dx": ["SET DX 1"],
       "P": ["SET DECL 1", "SET DECLMINE 0", "SET DECLFN 1"]}
for d in ("logs", "data"): os.makedirs(f"{E}/{d}", exist_ok=True)
SYL = ["ka", "lo", "mi", "ne", "ru", "sa", "ti", "vo", "ze", "pa", "do", "fi", "gu", "he", "jo", "be", "ra", "ki", "mo", "nu"]

def namer(rng, used):
    def name(k=3, suffix=""):
        while True:
            s = "".join(rng.choice(SYL) for _ in range(k)) + suffix
            if s not in used: used.add(s); return s
    return name

def T(f): return f"{f[1]} {f[0]} {f[2]}"     # fact tuple (rel, a, b) -> text

# =============== worlds: base records, one-value schema, and scenario instances ===============
# An instance: dict(sc, obs=[observation dicts in arrival order], probes=[...]).
# Observation: dict(src, key, t, rev, scope, facts=[(rel,a,b)]).
# Probe: (kind, rel, x, v, truth, tag) with kind in one/set/has/held/conflict.

def people(seed):
    w = blind_world(seed, 0.5); Tr, Ent, obs, info = w["T"], w["E"], [tuple(f) for f in w["observed"]], w["info"]
    rng = random.Random(seed * 101 + 7)
    region = dict(map(tuple, Tr["is located in"])); tl = dict(map(tuple, Tr["lives in"])); tf = dict(map(tuple, Tr["is from"]))
    rec = collections.defaultdict(list)
    for f in obs: rec[f[1]].append(f)
    known_loc = {a for (p, a, b) in obs if p == "is located in"} | {b for (p, a, b) in obs if p == "contains"}
    wrong = {x[1] for x in info["wrong"]}
    stated = lambda x, p: [f[2] for f in rec[x] if f[0] == p]
    elig = sorted(x for x in rec if x in tl and stated(x, "lives in") == [tl[x]] and x not in wrong and x not in info["sparse"])
    rng.shuffle(elig)
    with_from = [x for x in elig if stated(x, "is from") == [tf[x]]]
    no_from = [x for x in elig if not stated(x, "is from")]
    with_job = [x for x in elig if len(stated(x, "works as")) == 1]
    used = set(); pick = lambda pool, n: [x for x in pool if x not in used][:n]
    def take(pool, n): xs = pick(pool, n); used.update(xs); return xs
    S = Ent["settlement"]; G = sorted(set(region.values()))
    n = 15; inst = []
    def snap(x, t, facts, rev=1, src="census"): return {"src": src, "key": x, "t": t, "rev": rev, "scope": "snapshot", "facts": facts}
    def part(x, t, facts, src="census"): return {"src": src, "key": x, "t": t, "rev": 1, "scope": "partial", "facts": facts}
    def swap(x, rel, old, new, facts=None):
        return [(p, a, new) if (p == rel and a == x and b == old) else (p, a, b) for (p, a, b) in (facts if facts is not None else rec[x])]
    for x in take(with_from, n):   # ch: change, source also updates the stated is-from
        A = tl[x]; B = rng.choice([s for s in S if region[s] != region[A] and s in known_loc])
        f2 = swap(x, "is from", tf[x], region[B], swap(x, "lives in", A, B))
        inst.append({"sc": "ch", "obs": [snap(x, 2, f2)], "probes": [("one", "lives in", x, None, B, ""), ("one", "is from", x, None, region[B], "stated_updated"),
                                                                     ("held", "lives in", x, A, "past", "")]})
    for x in take(no_from, n):     # ch (derived-only variant): the region is only derivable
        A = tl[x]; B = rng.choice([s for s in S if region[s] != region[A] and s in known_loc])
        inst.append({"sc": "ch", "obs": [snap(x, 2, swap(x, "lives in", A, B))], "probes": [("one", "lives in", x, None, B, ""), ("one", "is from", x, None, region[B], "derived_only"),
                                                                                          ("held", "lives in", x, A, "past", "")]})
    for x in take(with_from, n):   # stale: the source leaves its is-from field unchanged
        A = tl[x]; B = rng.choice([s for s in S if region[s] != region[A] and s in known_loc])
        inst.append({"sc": "stale", "obs": [snap(x, 2, swap(x, "lives in", A, B))], "probes": [("one", "is from", x, None, region[B], "stale_field"), ("one", "lives in", x, None, B, "")]})
    for x in take(with_from, n):   # samereg: move within the region, is-from still true
        A = tl[x]; cands = [s for s in S if s != A and region[s] == region[A]]
        if not cands: continue
        B = rng.choice(cands)
        inst.append({"sc": "samereg", "obs": [snap(x, 2, swap(x, "lives in", A, B))], "probes": [("one", "is from", x, None, tf[x], "still_true"), ("one", "lives in", x, None, B, "")]})
    for x in take(elig, n):        # multi: a second, simultaneous residence
        A = tl[x]; C = rng.choice([s for s in S if s != A])
        inst.append({"sc": "multi", "obs": [snap(x, 2, rec[x] + [("lives in", x, C)])], "probes": [("set", "lives in", x, None, frozenset({A, C}), ""), ("conflict", "lives in", x, None, False, "")]})
    corr = [e for e in info["wrong"] if e[3] == "replaced" and e[0] in ("lives in", "works as") and e[1] in rec and e[1] not in used][:n]
    for (pred, x, bad, _, good) in corr:   # corr: revision 2 at t1 corrects the observation
        used.add(x)
        inst.append({"sc": "corr", "obs": [snap(x, 1, swap(x, pred, bad, good), rev=2)], "probes": [("one", pred, x, None, good, ""), ("held", pred, x, bad, "never", "")]})
    for x in take(elig, n):        # src: an independent source disagrees
        A = tl[x]; C = rng.choice([s for s in S if s != A])
        inst.append({"sc": "src", "obs": [part(x, 2, [("lives in", x, C)], src="survey")], "probes": [("conflict", "lives in", x, None, True, ""), ("one", "lives in", x, None, A, "")]})
    people_all = sorted(rec.keys() & set(tl))
    vol_places = rng.sample(S, 6)
    for x in take(elig, n):        # compat: compatible information from another source
        Y = rng.choice([p for p in people_all if p != x]); Sv = rng.choice(vol_places)
        inst.append({"sc": "compat", "obs": [part(x, 2, [("knows", x, Y), ("volunteers at", x, Sv)], src="survey")],
                     "probes": [("conflict", "*", x, None, False, ""), ("has", "knows", x, Y, True, "")]})
    for x in take(no_from, n):     # miss: the new settlement's region is unknown
        A = tl[x]; cands = [s for s in S if region[s] != region[A] and s not in known_loc]
        if not cands: continue
        B = rng.choice(cands)
        inst.append({"sc": "miss", "obs": [snap(x, 2, swap(x, "lives in", A, B))], "probes": [("one", "is from", x, None, region[B], "abstain_expected")]})
    for x in take(with_job, n):    # part1: partial update of a one-value field
        J = stated(x, "works as")[0]; J2 = rng.choice([j for j in Ent["profession"] if j != J])
        inst.append({"sc": "part1", "obs": [part(x, 2, [("works as", x, J2)])], "probes": [("one", "works as", x, None, J2, "")]})
    for x in take(elig, n):        # part2: a partial update that omits the record's other facts
        Y = rng.choice([p for p in people_all if p != x])
        inst.append({"sc": "part2", "obs": [part(x, 2, [("knows", x, Y)])], "probes": [("one", "lives in", x, None, tl[x], ""), ("has", "knows", x, Y, True, "")]})
    for x in take(elig, n):        # ooo: t3 arrives first, then t2, then t3 again
        A = tl[x]; B = rng.choice([s for s in S if s != A]); C = rng.choice([s for s in S if s not in (A, B)])
        o2 = snap(x, 2, swap(x, "lives in", A, B)); o3 = snap(x, 3, swap(x, "lives in", A, C))
        inst.append({"sc": "ooo", "obs": ([o3, dict(o3), o2] if os.environ.get("LATE") == "1" else [o3, o2, dict(o3)]), "probes": [("one", "lives in", x, None, C, ""), ("held", "lives in", x, B, "past", ""), ("held", "lives in", x, A, "past", "")]})
    for x in take(elig, n):        # vol: two partial observations in a new many-value relation
        S1, S2 = rng.sample(vol_places, 2)
        inst.append({"sc": "vol", "obs": [part(x, 2, [("volunteers at", x, S1)]), part(x, 3, [("volunteers at", x, S2)])],
                     "probes": [("set", "volunteers at", x, None, frozenset({S1, S2}), ""), ("conflict", "volunteers at", x, None, False, "")]})
    base = [snap(x, 1, fs) for x, fs in sorted(rec.items())]
    one = {"lives in", "works as", "is located in", "is from"}
    rels = ["lives in", "is from", "works as", "knows", "volunteers at"]
    true_rules = {(t, a, b if t != "I" else None, c) for t, a, b, c in EXPRESSIBLE_TRUE_RULES}
    return {"name": "people", "base": base, "inst": inst, "one": one, "rels": rels, "true_rules": true_rules, "decoys": set(DECOY_RULES), "preds": w["preds"] + ["volunteers at"]}

def database(seed):
    rng = random.Random(seed * 211 + 3); used = set(); nm = namer(rng, used)
    D = [nm(2, "dept") for _ in range(15)]; M = [nm(3) for _ in range(25)]; V = [nm(2, "div") for _ in range(4)]
    Pj = [nm(2, "proj") for _ in range(30)]; Cl = [nm(2, "co") for _ in range(10)]; Em = [nm(3) for _ in range(220)]
    mgr = {d: M[i] for i, d in enumerate(D)}; spare = M[15:]; div = {d: rng.choice(V) for d in D}
    dept = {e: rng.choice(D) for e in Em}; proj = {e: set(rng.sample(Pj, rng.choice([1, 2, 3]))) for e in Em}; serves = {p: rng.choice(Cl) for p in Pj}
    st_rep = {e for e in Em if rng.random() < 0.5}; st_bel = {e for e in Em if rng.random() < 0.3}
    def erow(e, d=None, ps=None, rep=True):
        d = d or dept[e]; ps = proj[e] if ps is None else ps
        fs = [("works in", e, d)] + [("assigned to", e, p) for p in sorted(ps)]
        if rep and e in st_rep: fs.append(("reports to", e, mgr[d] if d in mgr else mgr[dept[e]]))
        if rep and e in st_bel: fs.append(("belongs to", e, div[d]))
        return fs
    rows = {e: erow(e) for e in Em}
    for d in D: rows[d] = [("is managed by", d, mgr[d]), ("is part of", d, div[d])]
    for p in Pj: rows[p] = [("serves", p, serves[p])]
    snap = lambda k, t, fs, rev=1, src="hr": {"src": src, "key": k, "t": t, "rev": rev, "scope": "snapshot", "facts": fs}
    inst = []; taken = set()
    mgr_depts = rng.sample(D, 3)
    for d in mgr_depts:            # db_mgr: a department's manager changes; employee rows keep the old reports-to
        new = spare.pop(); emps = [e for e in Em if dept[e] == d]; taken.update(emps)
        probes = [("one", "is managed by", d, None, new, ""), ("held", "is managed by", d, mgr[d], "past", "")]
        probes += [("one", "reports to", e, None, new, "stale_field" if e in st_rep else "derived_only") for e in emps]
        inst.append({"sc": "db_mgr", "obs": [snap(d, 2, [("is managed by", d, new), ("is part of", d, div[d])])], "probes": probes})
    free = [e for e in Em if e not in taken]; rng.shuffle(free); it = iter(free); n = 15
    other_dept = lambda e, *ex: rng.choice([d for d in D if d != dept[e] and d not in mgr_depts and d not in ex])
    for _ in range(n):             # db_move
        e = next(it); d2 = other_dept(e)
        inst.append({"sc": "db_move", "obs": [snap(e, 2, erow(e, d2))], "probes": [("one", "works in", e, None, d2, ""), ("one", "reports to", e, None, mgr[d2], "stated_updated" if e in st_rep else "derived_only"),
                                                                              ("held", "works in", e, dept[e], "past", "")]})
    for _ in range(n):             # db_proj: one project removed, one added
        e = next(it); old = sorted(proj[e]); drop = old[0]; add = rng.choice([p for p in Pj if p not in proj[e]]); new = (set(old) - {drop}) | {add}
        inst.append({"sc": "db_proj", "obs": [snap(e, 2, erow(e, ps=new))], "probes": [("set", "assigned to", e, None, frozenset(new), ""), ("held", "assigned to", e, drop, "past", "")]})
    for _ in range(n):             # db_corr: the base row had the wrong department (no derived fields), revision 2 corrects it
        e = next(it); bad = other_dept(e); rows[e] = [("works in", e, bad)] + [("assigned to", e, p) for p in sorted(proj[e])]
        good = [("works in", e, dept[e])] + [("assigned to", e, p) for p in sorted(proj[e])]
        inst.append({"sc": "db_corr", "obs": [snap(e, 1, good, rev=2)], "probes": [("one", "works in", e, None, dept[e], ""), ("held", "works in", e, bad, "never", "")]})
    for _ in range(n):             # db_src
        e = next(it); dx = other_dept(e)
        inst.append({"sc": "db_src", "obs": [{"src": "payroll", "key": e, "t": 2, "rev": 1, "scope": "partial", "facts": [("works in", e, dx)]}],
                     "probes": [("conflict", "works in", e, None, True, ""), ("one", "works in", e, None, dept[e], "")]})
    for _ in range(n):             # db_ooo
        e = next(it); d2 = other_dept(e); d3 = other_dept(e, d2); o2, o3 = snap(e, 2, erow(e, d2)), snap(e, 3, erow(e, d3))
        inst.append({"sc": "db_ooo", "obs": ([o3, dict(o3), o2] if os.environ.get("LATE") == "1" else [o3, o2, dict(o3)]), "probes": [("one", "works in", e, None, d3, ""), ("held", "works in", e, d2, "past", "")]})
    base = [snap(k, 1, fs) for k, fs in sorted(rows.items())]
    return {"name": "database", "base": base, "inst": inst, "one": {"works in", "is managed by", "is part of", "serves", "reports to", "belongs to"},
            "rels": ["works in", "reports to", "is managed by", "assigned to", "belongs to"],
            "true_rules": {("C", "works in", "is managed by", "reports to"), ("C", "works in", "is part of", "belongs to")}, "decoys": set(),
            "preds": sorted(["works in", "reports to", "is managed by", "assigned to", "belongs to", "is part of", "serves"], key=len, reverse=True)}

def code(seed):
    rng = random.Random(seed * 307 + 11); used = set(); nm = namer(rng, used)
    Mo = [nm(2, "mod") for _ in range(12)]; F = [nm(3) for _ in range(160)]
    mod = {f: rng.choice(Mo) for f in F}; calls = {f: set(rng.sample([g for g in F if g != f], rng.choice([1, 2, 3]))) for f in F}
    manifest = {f for f in F if rng.random() < 0.4}
    deps = lambda f, cs=None, md=None: {(md or mod).get(g, mod.get(g)) for g in (calls[f] if cs is None else cs)}
    def row(f, cs=None, m=None, man_deps=None):
        cs = calls[f] if cs is None else cs
        fs = [("is defined in", f, m or mod[f])] + [("calls", f, g) for g in sorted(cs)]
        if f in manifest: fs += [("depends on", f, x) for x in sorted(man_deps if man_deps is not None else deps(f, cs))]
        return fs
    snap = lambda k, t, fs: {"src": "repo", "key": k, "t": t, "rev": 1, "scope": "snapshot", "facts": fs}
    inst = []; taken = set(); n = 15
    movers = [g for g in F if 2 <= sum(g in calls[f] for f in F) <= 5]; rng.shuffle(movers)
    for g in movers[:6]:           # code_move: g changes module; callers' manifests are not updated
        if g in taken: continue
        callers = [f for f in F if g in calls[f] and f not in taken and f != g]
        if not callers: continue
        M1 = mod[g]; M3 = rng.choice([m for m in Mo if m != M1]); taken.update(callers + [g])
        newmod = dict(mod); newmod[g] = M3
        probes = [("one", "is defined in", g, None, M3, "")]
        for f in callers:
            probes.append(("has", "depends on", f, M3, True, "new_dep"))
            probes.append(("has", "depends on", f, M1, M1 in deps(f, md=newmod), "stale_manifest" if f in manifest else "derived_only"))
        inst.append({"sc": "code_move", "obs": [snap(g, 2, row(g, m=M3))], "probes": probes})
    free = [f for f in F if f not in taken]; rng.shuffle(free)
    for f in free[:]:
        if len([x for x in inst if x["sc"] == "code_keep"]) >= n: break
        if f in taken: continue
        same = collections.defaultdict(list)
        for g in calls[f]: same[mod[g]].append(g)
        m2 = [m for m, gs in same.items() if len(gs) >= 2]
        if not m2: continue
        M1 = m2[0]; g = same[M1][0]; taken.add(f)
        inst.append({"sc": "code_keep", "obs": [snap(f, 2, row(f, calls[f] - {g}))], "probes": [("has", "depends on", f, M1, True, ""), ("has", "calls", f, g, False, "")]})
    for f in free:
        if len([x for x in inst if x["sc"] == "code_drop"]) >= n: break
        if f in taken: continue
        only = [g for g in calls[f] if sum(mod[h] == mod[g] for h in calls[f]) == 1]
        if not only or len(calls[f]) < 2: continue
        g = only[0]; taken.add(f)
        inst.append({"sc": "code_drop", "obs": [snap(f, 2, row(f, calls[f] - {g}))], "probes": [("has", "depends on", f, mod[g], False, "manifest_updated" if f in manifest else "derived_only"),
                                                                                         ("has", "calls", f, g, False, "")]})
    Mnew = nm(2, "mod"); helpers = [nm(3) for _ in range(n)]
    for f, h in zip([f for f in free if f not in taken][:n], helpers):   # code_add: a new module and a new call
        taken.add(f); mod[h] = Mnew; calls[h] = set()
        inst.append({"sc": "code_add", "obs": [snap(h, 2, [("is defined in", h, Mnew)]), snap(f, 2, row(f, calls[f] | {h}))],
                     "probes": [("has", "depends on", f, Mnew, True, "new_relationship"), ("has", "calls", f, h, True, "")]})
    for g in [f for f in free if f not in taken][:n]:   # code_ooo
        taken.add(g); M2, M3 = rng.sample([m for m in Mo if m != mod[g]], 2)
        o2, o3 = snap(g, 2, row(g, m=M2)), snap(g, 3, row(g, m=M3))
        inst.append({"sc": "code_ooo", "obs": ([o3, dict(o3), o2] if os.environ.get("LATE") == "1" else [o3, o2, dict(o3)]), "probes": [("one", "is defined in", g, None, M3, "")]})
    base = [snap(f, 1, row(f)) for f in F if f not in helpers]
    return {"name": "code", "base": base, "inst": inst, "one": {"is defined in"}, "rels": ["depends on", "calls", "is defined in"],
            "true_rules": {("C", "calls", "is defined in", "depends on")}, "decoys": set(), "preds": ["is defined in", "depends on", "calls"]}

WORLDS = {"people": people, "database": database, "code": code}

# =============== translating observations into each condition's native form ===============
def translate(wd, cond, arrivals):
    """arrivals: list of observations in arrival order (after the base). Translations for A/B/P are computed at the source,
    from each revision and the previous one in time order; they are delivered in arrival order."""
    hist = collections.defaultdict(list)   # (src,key) -> observations in source order
    for o in [*wd["base"], *arrivals]:
        k = (o["src"], o["key"])
        if not any(x["t"] == o["t"] and x["rev"] == o["rev"] and x["scope"] == o["scope"] for x in hist[k]): hist[k].append(o)
    for k in hist: hist[k].sort(key=lambda o: (o["t"], o["rev"]))
    def prev_state(o):
        st_ = set()
        for x in hist[(o["src"], o["key"])]:
            if (x["t"], x["rev"]) >= (o["t"], o["rev"]): break
            if x["t"] == o["t"] and x["rev"] < o["rev"]:   # an earlier revision at the same time is what this one corrects
                st_ = set(x["facts"]) if x["scope"] == "snapshot" else st_ | set(x["facts"]); continue
            st_ = set(x["facts"]) if x["scope"] == "snapshot" else st_ | set(x["facts"])
        return st_
    def is_corr(o): return any(x["t"] == o["t"] and x["rev"] < o["rev"] for x in hist[(o["src"], o["key"])])
    evid = {}
    def eid(o, i): return evid.setdefault((o["src"], o["key"], o["t"], o["rev"], i), "ev" + "".join(chr(97 + (len(evid) // 26 ** j) % 26) for j in range(3)))
    seen_vals = collections.defaultdict(list)   # (rel, subject) -> values in source order, for P's 'follows'
    cmds = []
    for o in arrivals:
        if cond in ("D", "Dx"):
            cmds.append(f"OBSERVE {o['src']} {o['key']} {o['t']} {o['rev']} {o['scope']} | " + " ; ".join(T(f) for f in o["facts"])); continue
        if cond == "C":
            cmds += [f"INGEST {T(f)}" for f in o["facts"]]; continue
        new = set(o["facts"]); prev = prev_state(o)
        if o["scope"] == "snapshot": removed, added = sorted(prev - new), sorted(new - prev)
        else: removed, added = [], sorted(new - prev)
        repl = []
        for r in list(removed):
            m = [a for a in added if a[0] == r[0] and a[1] == r[1] and r[0] in wd["one"]]
            if m: repl.append((r, m[0])); removed.remove(r); added.remove(m[0])
        corr = is_corr(o)
        for i, (old, nw) in enumerate(repl):
            if cond == "A": cmds.append(f"UPDATE {T(nw)}")
            elif cond == "B": cmds.append(f"AMEND {'CORRECT ' if corr else ''}{T(nw)}")
            elif cond == "P":
                e = eid(o, i); cmds += [f"INGEST {T(nw)}", f"INGEST {e} amends {nw[1]}", f"INGEST {e} replaces {old[2]}", f"INGEST {e} sets {nw[2]}"]
                if corr: cmds.append(f"INGEST {e} is correction")
        for r in removed:
            if cond in ("A", "B"): cmds.append(f"RETRACT {T(r)}")   # P has no vocabulary for removing a value
        for a in added: cmds.append(f"INGEST {T(a)}")
    return cmds

def base_cmds(wd, cond, path):
    if cond in ("D", "Dx"): return [f"OBSERVE {o['src']} {o['key']} {o['t']} {o['rev']} {o['scope']} | " + " ; ".join(T(f) for f in o["facts"]) for o in wd["base"]]
    open(path, "w").write("\n".join(T(f) for o in wd["base"] for f in o["facts"]) + "\n")
    return [f"INGESTFILE {path}"]

# =============== reading answers: one rule for every condition ===============
FLAGS = ("STALE", "CONTRADICTED", "CURRENT UNKNOWN", "SOURCES DISAGREE", "UNCERTAIN")
def read(out, preds):
    pat = re.compile(r"^  (\S+) (" + "|".join(re.escape(p) for p in sorted(set(preds), key=len, reverse=True)) + r") (\S+)\s+(stated.*|inferred.*|superseded.*|withdrawn.*|current.*|historical.*|corrected.*)$")
    facts = collections.defaultdict(list); conf = {}; flagged_subj = set(); was = []
    for l in out.splitlines():
        m = pat.match(l)
        if m: facts[(m.group(2), m.group(1))].append((m.group(3), m.group(4)))
        if l.startswith("CONFLICT\t"):
            m2 = re.search(r"stated: (\S+) (.+?) (\S+) \| inferred: \S+ .+? (\S+) \| because", l)
            if m2: conf[(m2.group(2), m2.group(1))] = None if m2.group(3) == m2.group(4) else m2.group(4); flagged_subj.add(m2.group(1)); continue
            m3 = re.match(r"CONFLICT\t(\S+)\t-\t.*\| relation: (.*)$", l)
            if m3: conf[(m3.group(2), m3.group(1))] = None; flagged_subj.add(m3.group(1))
        m4 = re.match(r"\[WAS\] (yes, current|yes, until|no: recorded in error|no record)", l)
        if m4: was.append(m4.group(1))
    for (rel, x), rows in facts.items():
        if any(s.startswith("stated,") and any(fl in s for fl in FLAGS) for v, s in rows): flagged_subj.add(x)
    return facts, conf, flagged_subj, was

def cur_values(facts, conf, rel, x):
    if (rel, x) in conf: return ("flag", None) if conf[(rel, x)] is None else ("vals", {conf[(rel, x)]})
    rows = facts.get((rel, x), [])
    if any(s.startswith("stated,") and any(fl in s for fl in FLAGS) and "STALE" not in s for v, s in rows): return ("flag", None)
    if any("STALE" in s for v, s in rows if s.startswith("stated")):
        alt = {v for v, s in rows if s.startswith("current")}
        return ("vals", alt) if alt else ("flag", None)
    vals = {v for v, s in rows if (s.startswith("stated") and not s.startswith("stated,")) or s.startswith("inferred")}
    return ("vals", vals)

def held(facts, rel, x, v):
    for val, s in facts.get((rel, x), []):
        if val != v: continue
        if s.startswith("superseded") and "(change" in s: return "past"
        if s.startswith("historical"): return "past"
        if s.startswith("superseded") and "(correction" in s: return "never"
        if s.startswith("withdrawn") or s.startswith("corrected"): return "never"
    for val, s in facts.get((rel, x), []):
        if val == v and s.startswith("stated") and not any(fl in s for fl in FLAGS): return "current"
        if val == v and s.startswith("stated"): return "unknown"
    return "no record"
WAS_MAP = {"yes, current": "current", "yes, until": "past", "no: recorded in error": "never", "no record": "no record"}

def score_probe(p, facts, conf, flagged, was_ans):
    kind, rel, x, v, truth, tag = p
    if kind == "conflict":
        fl = (x in flagged) if rel == "*" else (cur_values(facts, conf, rel, x)[0] == "flag")
        return ("right" if fl == truth else "wrong"), ("flag" if fl else "noflag")
    if kind == "held":
        h = was_ans if was_ans is not None else held(facts, rel, x, v)
        if h in ("no record", "unknown"): return "abstain", h
        return ("right" if h == truth else "wrong"), h
    k, vals = cur_values(facts, conf, rel, x)
    if k == "flag": return "abstain", "flag"
    if kind == "one":
        if not vals: return "abstain", "none"
        if len(vals) > 1: return "ambiguous", "|".join(sorted(vals))
        a = next(iter(vals)); return ("right" if a == truth else "wrong"), a
    if kind == "set": return ("right" if frozenset(vals) == truth else "wrong"), "|".join(sorted(vals))
    if kind == "has": a = v in vals; return ("right" if a == truth else "wrong"), str(a)

# =============== running ===============
def run_world(wname, seed, conds, reps=1, persist=True, combined=False):
    full = WORLDS[wname](seed)
    groups = [full["inst"]] if combined else [[i for i in full["inst"] if i["sc"] == sc] for sc in dict.fromkeys(i["sc"] for i in full["inst"])]
    only = os.environ.get("ONLY"); groups = [g for g in groups if not only or g[0]["sc"] in only.split(",")]
    res = []
    for gi, ginst in enumerate(groups):
        wd = dict(full); wd["inst"] = ginst
        res += run_session(wd, wname, seed, conds, reps, persist, "all" if combined else ginst[0]["sc"])
    return res

def run_session(wd, wname, seed, conds, reps, persist, label):
    rounds = max(len(i["obs"]) for i in wd["inst"])
    arrivals = [i["obs"][r] for r in range(rounds) for i in wd["inst"] if r < len(i["obs"])]
    probes = [p for i in wd["inst"] for p in [(i["sc"],) + q for q in i["probes"]]]
    res = []
    for cond in conds:
        tag = f"{wname}_s{seed}_{label}_{cond}"
        bc = base_cmds(wd, cond, f"{E}/data/{wname}_s{seed}_base.txt")
        uc = translate(wd, cond, arrivals)
        asks = ["RELATIONS", "INFER ALL", "CONFLICTS"] + [f"ASK ? {r} ?" for r in wd["rels"]]
        wasq = [f"WAS {p[3]} {p[2]} {p[4]}" for p in probes if p[1] == "held"] if cond == "B" else []
        save = f"{E}/data/{tag}.vtx2"
        for f_ in (save, save + ".amend", save + ".obs"):
            if os.path.exists(f_): os.remove(f_)
        script = PRE[cond] + bc + uc + asks + wasq + (["ECHO_SPLIT", f"SAVE {save}", f"LOAD {save}"] + asks[1:] + wasq if persist else []) + ["EXIT"]
        open(f"{E}/data/{tag}.cmds", "w").write("\n".join(script) + "\n")
        times = []
        for _ in range(reps):
            t0 = time.time(); out = subprocess.run([BIN[cond]], input="\n".join(script) + "\n", capture_output=True, text=True).stdout; times.append(time.time() - t0)
        open(f"{E}/logs/{tag}.log", "w").write(out)
        pre, post = (out.split("Unknown command. Type HELP.", 1) + [""])[:2]
        facts, conf, flagged, was = read(pre, wd["preds"])
        rows = []; wi = 0
        for p in probes:
            sc = p[0]; q = p[1:]
            wa = None
            if q[0] == "held" and cond == "B": wa = WAS_MAP[was[wi]]; wi += 1
            g, ans = score_probe(q, facts, conf, flagged, wa)
            rows.append({"sc": sc, "kind": q[0], "rel": q[1], "x": q[2], "tag": q[5], "grade": g, "ans": ans, "truth": str(q[4])})
        persist_ok = None
        if persist:
            f2, c2, fl2, w2 = read(post, wd["preds"])
            persist_ok = (dict(f2) == dict(facts) and c2 == conf and fl2 == flagged and w2 == was)
        rules = parse_rules(pre.splitlines())
        acc = {(r["type"], *[re.sub(r"\?\s*|\s*\?", "", x).strip() if x else None for x in (r["r1"], r["r2"] if r["type"] != "I" else None, r["r3"])]) for r in rules if r["accepted"]}
        sz = sum(os.path.getsize(f_) for f_ in (save, save + ".amend", save + ".obs") if os.path.exists(f_))
        upd_bytes = sum(len(c) + 1 for c in uc)
        res.append({"world": wname, "seed": seed, "cond": cond, "session": label, "seconds": round(st.median(times), 3), "probes": rows, "persist": persist_ok,
                    "true_rules": len(acc & wd["true_rules"]), "decoys": len(acc & wd["decoys"]), "accepted_rules": len(acc),
                    "save_bytes": sz, "update_cmds": len(uc), "update_bytes": upd_bytes, "n_obs": len(arrivals)})
        c = collections.Counter((r["sc"], r["grade"]) for r in rows)
        print(f"{wname:8} s{seed} {label:9} {cond:2} t={st.median(times):.2f}s rules={len(acc & wd['true_rules'])}/{len(wd['true_rules'])} persist={persist_ok} " +
              " ".join(f"{sc}:{c[(sc, 'right')]}/{sum(v for (s2, g), v in c.items() if s2 == sc)}" for sc in dict.fromkeys(r['sc'] for r in rows)), flush=True)
    return res

def run_base_only(wname, seed, conds):
    """No updates: ordinary rule discovery on the base KB, for the regression check (H7)."""
    wd = WORLDS[wname](seed); out = {}
    for cond in conds:
        script = PRE[cond] + base_cmds(wd, cond, f"{E}/data/{wname}_s{seed}_base.txt") + ["RELATIONS", "EXIT"]
        o = subprocess.run([BIN[cond]], input="\n".join(script) + "\n", capture_output=True, text=True).stdout
        rules = parse_rules(o.splitlines())
        acc = {(r["type"], *[re.sub(r"\?\s*|\s*\?", "", x).strip() if x else None for x in (r["r1"], r["r2"] if r["type"] != "I" else None, r["r3"])]) for r in rules if r["accepted"]}
        out[cond] = {"true_rules": len(acc & wd["true_rules"]), "decoys": len(acc & wd["decoys"]), "accepted_rules": len(acc),
                     "rule_set": sorted(map(str, acc))}
    return out

if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [11, 12, 13, 14, 15]
    conds = sys.argv[2].split(",") if len(sys.argv) > 2 else ["A", "B", "C", "D", "Dx", "P"]
    worlds = sys.argv[3].split(",") if len(sys.argv) > 3 else ["people", "database", "code"]
    reps = int(os.environ.get("REPS", "1"))
    out = {"runs": [], "base_only": []}
    resf = os.environ.get("RESULTS", f"{E}/results_main.json")
    for seed in seeds:
        for wn in worlds:
            out["runs"] += run_world(wn, seed, conds, reps, combined=os.environ.get("COMBINED") == "1")
            b = run_base_only(wn, seed, conds); out["base_only"].append({"world": wn, "seed": seed, **{c: b[c] for c in b}})
            json.dump(out, open(resf, "w"), indent=1)
