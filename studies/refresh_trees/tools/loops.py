"""R3-R6: tree programs executed across passes with REFRESH, in lockstep with a full-relearn engine.

  python3 loops.py [BINARY]      writes ../results_loops.json  (default binary: build/voltex2)

Programs: P1, the mod-3 state machine (studies/inferred_program), and the busy beaver and binary increment
(studies/harness, round 2 encoding). Each runs with ONE recycled step entity: every step retracts the previous state
facts and ingests the new ones, with words that already exist. Two engines run the same fact sequence: REFRESH 0.05
(the new path) and REFRESH 0 (full relearn every step). Every answer is compared between them and with the simulator.
"""
import json, os, random, statistics, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "studies", "inferred_program", "tools"))
sys.path.insert(0, os.path.join(ROOT, "studies", "harness", "tools"))
import importlib.util  # noqa: E402
import egm  # noqa: E402
import tm      # noqa: E402  (studies/harness: machines, encoding, simulator)
# studies/inferred_program/tools/run.py by path: studies/harness/tools also has a run.py
_spec = importlib.util.spec_from_file_location("ip_run", os.path.join(ROOT, "studies", "inferred_program", "tools", "run.py"))
ip = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ip)   # P1 examples, gate builder, FSM
BIN = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "voltex2")
TMP = tempfile.mkdtemp()


def open_pair(lines, extra):
    p = os.path.join(TMP, f"kb{random.random()}.txt"); open(p, "w").write("\n".join(lines) + "\n")
    words = len({w for l in lines for w in l.split()})
    st = dict(DEPTH=0, TENDENCYSTEPS=0, PROFILE=1, MAXWORDS=max(12000, words + 1000), **extra)
    return (egm.open(p, settings=dict(st, REFRESH=0.05), binary=BIN), egm.open(p, settings=dict(st, REFRESH=0), binary=BIN))


def step(engines, retract, ingest, questions):
    """Apply the same change to both engines, then ask. Returns (answers per engine, builds per engine, seconds per engine)."""
    out = []
    for e in engines:
        t = time.time()
        for f in retract: e.retract(f)
        e.ingest_many(ingest)
        prof = e.cmd(f"ASK {questions[0]}")
        ans = [tuple(sorted(x.object for x in e.ask(q, strict=True) if x.status != "stated")) for q in questions]
        full = sum("rule mining" in l for l in prof); refresh = sum("refresh:" in l for l in prof)
        out.append((ans, full, refresh, time.time() - t))
    return out


def run_p1(bits):
    nm = ip.Names("q"); L = ip.p1_examples(nm)
    W, X = nm(), nm(); gl, O = ip.gate(nm, "step", [(W, None), (X, None)])
    s = "s0"; cur = [f"{W} has value {s}", f"{X} has value {bits[0]}"]
    new, full = open_pair(L + gl + cur, {"TREES": 1})
    for e in (new, full): e.cmd("RELATIONS")
    rows = []
    for i, b in enumerate(bits):
        nxt = [f"{W} has value {s}", f"{X} has value {b}"]
        (an, fn, rn, tn), (af, ff, rf, tf) = step((new, full), cur if i else [], nxt if i else [], [f"{O} has value ?"])
        cur = nxt; truth = ip.FSM[(s, b)]
        rows.append({"new": an[0], "full": af[0], "truth": truth, "new_full_builds": fn, "new_refresh": rn,
                     "full_full_builds": ff, "ms_new": 1000 * tn, "ms_full": 1000 * tf})
        if an[0] != (truth,): break
        s = truth
    new.close(); full.close()
    return summarise("P1 state machine", rows)


def run_machine(prog, tape, head):
    names = tm.Names(77); rng = random.Random(0)
    L = tm.examples("bb3", 64, names, rng) + tm.examples("inc", 64, names, rng)
    st, w, mv, nx = "stp", "slw", "slm", "sln"   # one recycled step entity
    links = [f"{w} is write of {st}", f"{mv} is move of {st}", f"{nx} is next of {st}"]
    state, blank = tm.START[prog], tm.BLANK[prog]; tape = dict(tape)
    cur = [f"{st} has state {state}", f"{st} reads {tape.get(head, blank)}"]
    new, full = open_pair(L + links + cur, {"TREES": 1})
    for e in (new, full): e.cmd("RELATIONS")
    rows, first = [], True
    q = [f"{w} {tm.REL['write']} ?", f"{mv} {tm.REL['move']} ?", f"{nx} {tm.REL['next']} ?"]
    while state != "halt" and len(rows) < 200:
        sym = tape.get(head, blank); nxt = [f"{st} has state {state}", f"{st} reads {sym}"]
        (an, fn, rn, tn), (af, ff, rf, tf) = step((new, full), [] if first else cur, [] if first else nxt, q)
        first = False; cur = nxt
        truth = tm.PROGRAMS[prog][(state, sym)]
        rows.append({"new": an, "full": af, "truth": [[x] for x in truth], "new_full_builds": fn, "new_refresh": rn,
                     "full_full_builds": ff, "ms_new": 1000 * tn, "ms_full": 1000 * tf})
        if [list(x) for x in an] != [[x] for x in truth]: break
        tape[head] = truth[0]; head += 1 if truth[1] == "right" else -1; state = truth[2]
    new.close(); full.close()
    return summarise(f"{prog}", rows)


def summarise(name, rows):
    correct = sum(1 for r in rows if (list(r["new"]) == [r["truth"]] if isinstance(r["truth"], str) else [list(x) for x in r["new"]] == r["truth"]))
    return {"program": name, "steps": len(rows), "correct": correct,
            "new_equals_full": sum(1 for r in rows if r["new"] == r["full"]),
            "new_full_builds": sum(r["new_full_builds"] for r in rows), "new_refresh_builds": sum(r["new_refresh"] for r in rows),
            "full_engine_full_builds": sum(r["full_full_builds"] for r in rows),
            "ms_per_step_new": round(statistics.median(r["ms_new"] for r in rows), 2) if rows else None,
            "ms_per_step_full": round(statistics.median(r["ms_full"] for r in rows), 2) if rows else None}


def r6():
    """Safety: (a) a new word mid-run forces a full build; (b) a rule whose relation vanishes is dropped."""
    nm = ip.Names("z"); L = ip.p1_examples(nm); W, X = nm(), nm(); gl, O = ip.gate(nm, "step", [(W, None), (X, None)])
    cur = [f"{W} has value s0", f"{X} has value b1"]
    p = os.path.join(TMP, "r6.txt"); open(p, "w").write("\n".join(L + gl + cur) + "\n")
    with egm.open(p, settings=dict(DEPTH=0, TENDENCYSTEPS=0, PROFILE=1, TREES=1, REFRESH=0.05, MAXWORDS=12000), binary=BIN) as e:
        e.cmd("RELATIONS")
        e.retract(cur[1]); e.ingest(f"{X} has value b0"); p1 = e.cmd(f"ASK {O} has value ?")
        e.ingest("brandnewword has value s0"); p2 = e.cmd(f"ASK {O} has value ?")
        a = {"refresh_before_new_word": any("refresh:" in l for l in p1), "full_after_new_word": any("rule mining" in l for l in p2)}
    # (b) composition rule over a 3-fact relation; retracting one fact drops the relation below 3 records
    people = [f"pp{i} lives in city{i % 3}" for i in range(30)] + [f"pp{i} is from land{i % 3}" for i in range(20)]
    lies = [f"city{c} lies in land{c}" for c in range(3)]
    p = os.path.join(TMP, "r6b.txt"); open(p, "w").write("\n".join(people + lies) + "\n")
    res = {}
    for refresh in (0.05, 0):
        with egm.open(p, settings=dict(PROFILE=1, REFRESH=refresh), binary=BIN) as e:
            e.cmd("RELATIONS"); before = [x.text for x in e.rules() if "lies in" in x.text]
            # net change 0 (a retract plus an ingest of existing words), so the refresh path's size condition holds; a
            # retract alone underflows the unsigned change counter and always forces a full build (DEVIATIONS.md 1)
            e.retract(lies[0]); e.ingest("pp0 lives in city1"); out = e.cmd("ASK pp25 is from ?")
            after = [x.text for x in e.rules() if "lies in" in x.text]
            res[refresh] = {"rules_with_relation_before": len(before), "after": len(after),
                            "refresh_taken": any("refresh:" in l for l in out),
                            "answers": sorted(x.object for x in e.ask("pp25 is from ?") if x.status != "stated"),
                            "relations": sorted(r.relation for r in e.relations())}
    b = {"refresh": res[0.05], "full": res[0], "same_answers": res[0.05]["answers"] == res[0]["answers"],
         "same_rules_after": res[0.05]["after"] == res[0]["after"]}
    return {"a_new_word": a, "b_vanished_relation": b}


def main():
    r = random.Random(5); bits = [r.choice(["b0", "b1"]) for _ in range(64)]
    R = {"binary": os.path.basename(BIN), "programs": [run_p1(bits), run_machine("bb3", {}, 0)]}
    for L in (4, 8, 16):
        R["programs"].append(run_machine("inc", {i: "one" for i in range(L)}, L - 1))
    R["safety"] = r6()
    for p in R["programs"]: print(p, flush=True)
    print(json.dumps(R["safety"], indent=1))
    json.dump(R, open(os.path.join(HERE, "..", "results_loops" + ("_asan" if "asan" in BIN else "") + ".json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
