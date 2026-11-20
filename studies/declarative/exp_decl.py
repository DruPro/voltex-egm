"""Declarative amendments study (PREREGISTRATION.md). Conditions A (UPDATE), B (AMEND, V2b), C1/C2 (declarative ingestion).
Usage: python3 exp_decl.py [seeds] [conditions]"""
import sys, os, re, json, random, time, subprocess, statistics as st, collections
sys.path.insert(0, "/home/claude/work/improve")
from harness import world, parse_rules
sys.path.insert(0, "/home/claude/work/blind/hidden")
from world import EXPRESSIBLE_TRUE_RULES, DECOY_RULES
sys.argv_saved = sys.argv; sys.argv = sys.argv[:1]
exec(open("/home/claude/work/amend/exp_amend.py").read().split("if __name__")[0])   # make_moves, norm_rule (unchanged from the earlier study)
sys.argv = sys.argv_saved

W = "/home/claude/work"; D = f"{W}/declarative"
BIN = {"A": f"{W}/v21/voltex2", "B": f"{W}/amend/voltex2_amend", "C1": f"{D}/voltex2_decl", "C2": f"{D}/voltex2_decl"}
PRE = {"A": [], "B": ["SET EXPLAIN 2", "SET DEPEV 0", "SET SUSPECT 0"], "C1": ["SET DECL 1", "SET DECLMINE 1"], "C2": ["SET DECL 1", "SET DECLMINE 0"],
       "C2fn": ["SET DECL 1", "SET DECLMINE 0", "SET DECLFN 1"]}
BIN["C2fn"] = BIN["C2"]
os.makedirs(f"{D}/logs", exist_ok=True); os.makedirs(f"{D}/data", exist_ok=True)
AMEND_WORDS = re.compile(r"\b(amends|replaces|sets|follows|withdraws|correction)\b")

class Ids:
    def __init__(self): self.n = 0
    def __call__(self):
        self.n += 1; k = self.n; s = ""
        while True:
            s = chr(97 + k % 26) + s; k //= 26
            if k == 0: break
        return "ev" + s

# ---- one event, expressed in each condition's native form ----
def ev_change(cond, X, rel, A, B, eid, corr=False, follows=None):
    if cond == "A": return [f"UPDATE {X} {rel} {B}"]
    if cond == "B": return [f"AMEND {'CORRECT ' if corr else ''}{X} {rel} {B}"]
    out = [f"INGEST {X} {rel} {B}", f"INGEST {eid} amends {X}", f"INGEST {eid} replaces {A}", f"INGEST {eid} sets {B}"]
    if corr: out.append(f"INGEST {eid} is correction")
    if follows: out.append(f"INGEST {eid} follows {follows}")
    return out

def ev_withdraw(cond, X, rel, A, B, eid, wid):
    if cond == "A": return [f"UPDATE {X} {rel} {A}"]
    if cond == "B": return [f"AMEND CORRECT {X} {rel} {A}"]
    return [f"INGEST {wid} withdraws {eid}"]

def ev_plain(cond, X, rel, B): return [f"INGEST {X} {rel} {B}"]

# ---- reading answers: the same rule for every condition ----
def read_session(out, preds):
    lines = out.splitlines()
    pat = re.compile(r"^  (\S+) (" + "|".join(re.escape(p) for p in preds) + r") (\S+)\s+(stated.*|inferred.*|superseded.*|withdrawn.*|current.*)$")
    facts = collections.defaultdict(list)            # (rel, subj) -> [(value, status)]
    for l in lines:
        m = pat.match(l)
        if m: facts[(m.group(2), m.group(1))].append((m.group(3), m.group(4)))
    conf = {}
    for l in lines:
        if not l.startswith("CONFLICT\t"): continue
        m = re.search(r"stated: (\S+) (.+?) (\S+) \| inferred: \S+ .+? (\S+) \| because (.*)", l)
        if m:
            s_val, i_val = m.group(3), m.group(4)
            conf[(m.group(2), m.group(1))] = None if i_val == s_val else i_val
            continue
        m = re.match(r"CONFLICT\t(\S+)\t-\t.*\| relation: (.*)$", l)
        if m: conf[(m.group(2), m.group(1))] = None
    was = {}
    for l in lines:
        m = re.match(r"\[WAS\] (yes, current|yes, until|no: recorded in error|no record)", l)
        if m: was.setdefault("_order", []).append(m.group(1))
    hist = collections.Counter()
    for l in lines:
        m = re.match(r"  #\d+ (changed|corrected): '(\S+) .*?' ->", l)
        if m: hist[m.group(2)] += 1
    return facts, conf, was.get("_order", []), hist

def current(facts, conf, rel, x):
    """right/wrong are judged by the caller; here: value, or ('ambiguous', values), or None (abstains)."""
    if (rel, x) in conf: return conf[(rel, x)]
    rows = facts.get((rel, x), [])
    if any(s.startswith("stated, CONTRADICTED") or s.startswith("stated, CURRENT UNKNOWN") for v, s in rows): return None
    stated = sorted({v for v, s in rows if s.startswith("stated") and "STALE" not in s})
    if len(stated) == 1: return stated[0]
    if len(stated) > 1: return ("ambiguous", tuple(stated))
    inf = sorted({v for v, s in rows if s.startswith("inferred")})
    return inf[0] if len(inf) == 1 else None

def held_from_ask(facts, rel, x, v):
    for val, s in facts.get((rel, x), []):
        if val != v: continue
        if s.startswith("superseded") and "(change" in s: return "past"
        if s.startswith("superseded") and "(correction" in s: return "never"
        if s.startswith("withdrawn"): return "never"
        if s.startswith("stated, CONTRADICTED") or s.startswith("stated, CURRENT UNKNOWN"): return "unknown"
        if s.startswith("stated"): return "current"
    return "no record"

WAS_MAP = {"yes, current": "current", "yes, until": "past", "no: recorded in error": "never", "no record": "no record"}

def grade(ans, truth):
    if ans is None or ans in ("no record", "unknown"): return "abstain"
    if isinstance(ans, tuple): return "ambiguous"
    return "right" if ans == truth else "wrong"

def run(cond, cmds, tag, reps=1):
    script = "\n".join(PRE[cond] + cmds + ["EXIT"]) + "\n"
    times, out = [], ""
    for _ in range(reps):
        t0 = time.time(); out = subprocess.run([BIN[cond]], input=script, capture_output=True, text=True).stdout; times.append(time.time() - t0)
    open(f"{D}/logs/{tag}_{cond}.log", "w").write(out)
    open(f"{D}/data/{tag}_{cond}.cmds", "w").write(script)
    return out, st.median(times)

# ---------------- S1: scale session ----------------
def s1(seed, conds, reps=3):
    w = world(seed, 0.5); T, E, obs = w["T"], w["E"], set(w["observed"])
    moves, region, true_lives = make_moves(w, seed, 0.15)
    rng = random.Random(seed * 77 + 5)
    stated_loc = {a: b for (p, a, b) in obs if p == "is located in"}
    stated_lives = collections.defaultdict(set)
    for (p, a, b) in obs:
        if p == "lives in": stated_lives[a].add(b)
    busy = {o for o, n in moves.values()} | {n for o, n in moves.values()}
    residents = collections.defaultdict(list)
    for p_, s_ in true_lives.items(): residents[s_].append(p_)
    cand = sorted(s for s in stated_loc if s not in busy and stated_loc[s] == region[s] and any(s in stated_lives[r] for r in residents[s]))
    redraw = {}
    for s in rng.sample(cand, min(3, len(cand))): redraw[s] = (region[s], rng.choice([g for g in E["region"] if g != region[s]]))
    ids = Ids(); events = [("move", p, "lives in", o, n, ids()) for p, (o, n) in sorted(moves.items())]
    events += [("redraw", s, "is located in", a, b, ids()) for s, (a, b) in sorted(redraw.items())]
    probes = ["RELATIONS", "INFER ALL", "CONFLICTS", "ASK ? lives in ?", "ASK ? is from ?", "ASK ? is located in ?", "ASK ? contains ?"]
    res = {}
    for cond in conds:
        cmds = [f"INGESTFILE {w['path']}"]
        n_rec = 0; n_bytes = 0
        for kind, x, rel, a, b, eid in events:
            c = ev_change(cond, x, rel, a, b, eid); cmds += c
            n_rec += len(c); n_bytes += sum(len(l.split(" ", 1)[1]) + 1 for l in c)
        hist_cmds = []
        if cond == "B":
            for kind, x, rel, a, b, eid in events: hist_cmds.append(f"WAS {x} {rel} {a}")
        save = f"{D}/data/s1_s{seed}_{cond}.vtx2"
        for f_ in (save, save + ".amend"):
            if os.path.exists(f_): os.remove(f_)
        cmds2 = cmds + probes + hist_cmds + ["ECHO_SPLIT"] + [f"SAVE {save}", f"LOAD {save}"] + probes[1:] + hist_cmds
        out, sec = run(cond, cmds2, f"s1_s{seed}", reps)
        pre, post = out.split("Unknown command. Type HELP.", 1) if "Unknown command. Type HELP." in out else (out, "")
        facts, conf, was, hist = read_session(pre, w["preds"])
        tl_from = dict(map(tuple, T["is from"]))
        stated_from = {a: b for (p, a, b) in obs if p == "is from"}
        r = {"seed": seed, "cond": cond, "seconds": round(sec, 3), "events": len(events), "records_or_cmds": n_rec, "bytes": n_bytes,
             "save_bytes": os.path.getsize(save) + (os.path.getsize(save + ".amend") if os.path.exists(save + ".amend") else 0)}
        g = collections.Counter()
        for p, (o, n) in moves.items():
            g["P1_" + grade(current(facts, conf, "lives in", p), n)] += 1
            if stated_from.get(p) == tl_from.get(p):
                g["P2_" + grade(current(facts, conf, "is from", p), region[n])] += 1
            if cond == "B": h = WAS_MAP[was[[e[1] for e in events].index(p)]]
            elif cond == "A": h = "no record"
            else: h = held_from_ask(facts, "lives in", p, o)
            g["P3_" + grade(h, "past")] += 1
        for a, b in stated_from.items():
            if a in moves or a in {r_ for s in redraw for r_ in residents[s]} or b != tl_from.get(a): continue
            g["P4from_" + grade(current(facts, conf, "is from", a), b)] += 1
        for a in stated_lives:
            if a in moves or true_lives.get(a) not in stated_lives[a]: continue
            g["P4lives_" + grade(current(facts, conf, "lives in", a), true_lives[a])] += 1
        for s, (ra, rb) in redraw.items():
            g["P5_" + grade(current(facts, conf, "is located in", s), rb)] += 1
            if cond == "B": h = WAS_MAP[was[[e[1] for e in events].index(s)]]
            elif cond == "A": h = "no record"
            else: h = held_from_ask(facts, "is located in", s, ra)
            g["P6_" + grade(h, "past")] += 1
            if any(v == s and (st_.startswith("stated") or st_.startswith("inferred")) for v, st_ in facts.get(("contains", ra), [])):
                g["P5c_stale_inverse_asserted"] += 1
            g["P5c_n"] += 1
            for p in residents[s]:
                if p in moves: continue
                key = "P5r_stated_" if stated_from.get(p) == ra else ("P5r_derived_" if p not in stated_from else None)
                if key: g[key + grade(current(facts, conf, "is from", p), rb)] += 1
        rules = parse_rules(pre.splitlines())
        acc = {norm_rule(x) for x in rules if x["accepted"]}
        r["true_rules"] = len(acc & {(t, a, b if t != "I" else None, c) for t, a, b, c in EXPRESSIBLE_TRUE_RULES})
        r["decoys"] = len(acc & set(DECOY_RULES))
        r["amend_vocab_rules"] = sum(1 for l in pre.splitlines() if re.match(r"\s+ACCEPT \[", l) and AMEND_WORDS.search(l))
        r["amend_vocab_relations"] = sum(1 for l in pre.splitlines() if re.match(r"\s+#\d+\s", l) and AMEND_WORDS.search(l))
        # persistence: the probe answers after SAVE/LOAD must equal those before
        r["persist_identical"] = None
        if post:
            facts2, conf2, was2, _ = read_session(post, w["preds"])
            r["persist_identical"] = (dict(facts2) == dict(facts) and conf2 == conf and was2 == was)
        r.update(dict(g)); res[cond] = r
        print(f"S1 s{seed} {cond:2} t={sec:.2f}s " + " ".join(f"{k}={v}" for k, v in sorted(g.items())) + f" rules={r['true_rules']} decoys={r['decoys']} amendrules={r['amend_vocab_rules']} persist={r['persist_identical']}", flush=True)
    return res

# ---------------- S2: scenario session ----------------
def s2(seed, conds, only=None):
    w = world(seed, 0.5); T, E, obs, info = w["T"], w["E"], set(w["observed"]), w["info"]
    tl = dict(map(tuple, T["lives in"])); rng = random.Random(seed * 13 + 1)
    wrong_subj = {x[1] for x in info["wrong"]}
    stated_lives = collections.defaultdict(set)
    for (p, a, b) in obs:
        if p == "lives in": stated_lives[a].add(b)
    elig = sorted(a for a, vs in stated_lives.items() if vs == {tl.get(a)} and a not in wrong_subj and a not in info["sparse"])
    rng.shuffle(elig)
    k = min(20, len(elig) // 7)
    groups = {name: elig[i * k:(i + 1) * k] for i, name in enumerate(["B1", "D1", "D2", "D3", "E", "F1", "F2"])}
    S = E["settlement"]
    other = lambda *ex: rng.choice([s for s in S if s not in ex])
    corr = [x for x in info["wrong"] if x[3] == "replaced" and x[0] in ("lives in", "works as") and x[1] not in info["sparse"]][:20]
    ids = Ids(); inst = []
    for x in groups["B1"]: A = tl[x]; B = other(A); inst.append(("B1", x, "lives in", {"A": A, "B": B}, [[("c", A, B, ids(), False, None)]]))
    for (pred, x, bad, _, good) in corr: inst.append(("B2", x, pred, {"A": bad, "B": good}, [[("c", bad, good, ids(), True, None)]]))
    for x in groups["D1"]:
        A = tl[x]; B = other(A); C = other(A, B); inst.append(("D1", x, "lives in", {"A": A, "B": B, "C": C}, [[("c", A, B, ids(), False, None)], [("c", B, C, ids(), False, None)]]))
    for x in groups["D2"]:
        A = tl[x]; B = other(A); C = other(A, B); e1, e2 = ids(), ids()
        inst.append(("D2", x, "lives in", {"A": A, "B": B, "C": C}, [[("c", B, C, e2, False, None)], [("c", A, B, e1, False, None)]]))
    for x in groups["D3"]:
        A = tl[x]; B = other(A); e = ids(); inst.append(("D3", x, "lives in", {"A": A, "B": B}, [[("c", A, B, e, False, None)], [("c", A, B, e, False, None)]]))
    for x in groups["E"]: A = tl[x]; B = other(A); inst.append(("E", x, "lives in", {"A": A, "B": B}, [[("p", B)]]))
    for x in groups["F1"]:
        A = tl[x]; B = other(A); e = ids(); inst.append(("F1", x, "lives in", {"A": A, "B": B}, [[("c", A, B, e, False, None)], [("w", A, B, e, ids())]]))
    for x in groups["F2"]:
        A = tl[x]; B = other(A); e1, e2 = ids(), ids()
        inst.append(("F2", x, "lives in", {"A": A, "B": B}, [[("c", A, B, e1, False, None)], [("c", B, A, e2, False, e1)]]))
    if only: inst = [i for i in inst if i[0] in only]
    res = {}
    for cond in conds:
        cmds = [f"INGESTFILE {w['path']}"]
        for rnd in range(2):                                   # same arrival order for every condition
            for (sc, x, rel, v, rounds) in inst:
                if rnd >= len(rounds): continue
                for e in rounds[rnd]:
                    if e[0] == "c": cmds += ev_change(cond, x, rel, e[1], e[2], e[3], e[4], e[5])
                    elif e[0] == "w": cmds += ev_withdraw(cond, x, rel, e[1], e[2], e[3], e[4])
                    else: cmds += ev_plain(cond, x, rel, e[1])
        probes = ["RELATIONS", "INFER ALL", "CONFLICTS", "ASK ? lives in ?", "ASK ? works as ?"]
        hq = []
        held_targets = {"B1": [("A", "past")], "B2": [("A", "never")], "D1": [("B", "past"), ("A", "past")], "D2": [("B", "past"), ("A", "past")],
                        "D3": [("A", "past")], "F1": [("B", "never")], "F2": [("B", "past")]}
        for (sc, x, rel, v, rounds) in inst:
            for key, truth in held_targets.get(sc, []): hq.append((sc, x, rel, v[key], truth))
            if sc in ("D3", "F1") and cond == "B": pass
        hist_cmds = [f"WAS {x} {rel} {val}" for (sc, x, rel, val, truth) in hq] if cond == "B" else []
        hist_cmds += [f"HISTORY {x}" for (sc, x, rel, v, rounds) in inst if sc in ("D3", "F1")] if cond == "B" else []
        save = f"{D}/data/s2_s{seed}_{cond}.vtx2"
        for f_ in (save, save + ".amend"):
            if os.path.exists(f_): os.remove(f_)
        out, sec = run(cond, cmds + probes + hist_cmds + ["ECHO_SPLIT", f"SAVE {save}", f"LOAD {save}"] + probes[1:] + hist_cmds, f"s2_s{seed}" + ("_" + "".join(only) if only else ""))
        pre, post = out.split("Unknown command. Type HELP.", 1)
        facts, conf, was, _ = read_session(pre, w["preds"])
        g = collections.Counter()
        cur_truth = {"B1": "B", "B2": "B", "D1": "C", "D2": "C", "D3": "B", "F1": "A", "F2": "A"}
        for (sc, x, rel, v, rounds) in inst:
            ans = current(facts, conf, rel, x)
            if sc == "E":
                cat = "flagged" if ans is None else ("ambiguous_unflagged" if isinstance(ans, tuple) else ("single_new" if ans == v["B"] else "single_old"))
                g[f"E_{cat}"] += 1
            else:
                g[f"{sc}_cur_{grade(ans, v[cur_truth[sc]])}"] += 1
        wi = 0
        for (sc, x, rel, val, truth) in hq:
            if cond == "B": h = WAS_MAP[was[wi]]; wi += 1
            elif cond == "A": h = held_from_ask(facts, rel, x, val); h = "current" if h == "current" else "no record"
            else: h = held_from_ask(facts, rel, x, val)
            g[f"{sc}_held_{grade(h, truth)}"] += 1
        # D3: exactly one amendment recorded; F1: the withdrawn amendment is still visible in the record
        hb = collections.Counter()
        if cond == "B":
            cur_subj = None
            for l in pre.split("\n[WAS]")[-1].splitlines() if False else pre.splitlines():
                m = re.match(r"  #\d+ (changed|corrected): '(\S+) ", l)
                if m: hb[m.group(2)] += 1
        for (sc, x, rel, v, rounds) in inst:
            if sc == "D3":
                n_am = hb[x] if cond == "B" else (sum(1 for val, s in facts.get((rel, x), []) if s.startswith("superseded")) if cond.startswith("C") else None)
                g["D3_one_amendment"] += int(n_am == 1) if n_am is not None else 0
                g["D3_n"] += 1
            if sc == "F1":
                vis = (hb[x] >= 1) if cond == "B" else (any(s.startswith("withdrawn") for val, s in facts.get((rel, x), [])) if cond.startswith("C") else False)
                g["F1_log_kept"] += int(vis); g["F1_n"] += 1
        facts2, conf2, was2, _ = read_session(post, w["preds"])
        r = {"seed": seed, "cond": cond, "seconds": round(sec, 3), "persist_identical": dict(facts2) == dict(facts) and conf2 == conf and was2 == was,
             "n_inst": collections.Counter(i[0] for i in inst)}
        r.update(dict(g)); res[cond] = r
        print(f"S2 s{seed} {cond:2} " + " ".join(f"{k}={v}" for k, v in sorted(g.items())) + f" persist={r['persist_identical']}", flush=True)
    return res

if __name__ == "__main__":
    seeds = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1, 2, 3, 4, 5]
    conds = sys.argv[2].split(",") if len(sys.argv) > 2 else ["A", "B", "C1", "C2"]
    out = {"S1": [], "S2": []}
    mode = os.environ.get("MODE", "registered")
    for seed in seeds:
        if mode in ("registered", "fu2"):
            out["S1"] += list(s1(seed, conds).values())
            out["S2"] += list(s2(seed, conds).values())
        if mode == "fu1":                       # each scenario type in its own session
            for sc in ["B1", "B2", "D1", "D2", "D3", "E", "F1", "F2"]:
                out["S2"] += list(s2(seed, conds, only=[sc]).values())
        json.dump(out, open(os.environ.get("RESULTS", f"{D}/results_decl.json"), "w"), indent=1)
