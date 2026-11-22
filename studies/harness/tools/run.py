"""Experiments H1-H4 (PREREGISTRATION.md). Writes ../results/*.json and ../results/verdicts.json.

  python3 run.py
"""
import json, os, random, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "studies", "compute", "tools"))
import egm      # noqa: E402
import gen      # noqa: E402  (studies/compute: the gate World)
import tm       # noqa: E402
import harness  # noqa: E402
OBS = os.path.join(STUDY, "obs"); OUT = os.path.join(STUDY, "results" if tm.ROUND == "2" else "results_r1"); BIN = os.path.join(ROOT, "build", "voltex2")
ST = {"TREES": 1, "DEPTH": 0, "TENDENCYSTEPS": 0}
SEEDS = range(3)


def open_kb(name, lines):
    os.makedirs(OBS, exist_ok=True); p = os.path.join(OBS, name + ".txt")
    open(p, "w").write("\n".join(lines) + "\n")
    return egm.open(p, settings=ST, binary=BIN)


# ---------- H1 / H2 gates: teach, then ingest only a new circuit and ask -------------------------------------------
def adder8(W):
    """An 8-bit ripple-carry adder on W (only primary inputs stated). Returns (new lines, {output wire: value})."""
    start = len(W.lines); bit = lambda: W.r.randint(0, 1); G = lambda k, ins: W.gate(k, ins, False, "c")
    carry = W.wire(0, True); outs = []
    for _ in range(8):
        a, b = W.wire(bit(), True), W.wire(bit(), True)
        s1 = G("xor", [a, b]); outs.append(G("xor", [s1, carry]))
        carry = G("or", [G("and", [a, b]), G("and", [s1, carry])])
    outs.append(carry)
    return W.lines[start:], {w: gen.V[W.value[w]] for w in outs}


def mux(W):
    start = len(W.lines); bit = lambda: W.r.randint(0, 1); G = lambda k, ins: W.gate(k, ins, False, "c")
    a, b, s = W.wire(bit(), True), W.wire(bit(), True), W.wire(bit(), True)
    o = G("or", [G("and", [a, G("not", [s])]), G("and", [b, s])])
    return W.lines[start:], {o: gen.V[W.value[o]]}


def gates_run(seed, per_kind, n_adders=10, n_mux=0):
    W = gen.World(7000 + seed * 100 + per_kind)
    for k in ("and", "or", "xor"): W.examples(k, per_kind, 2)
    W.examples("not", max(1, per_kind // 2), 1)
    taught = list(W.lines)
    res = {"seed": seed, "per_kind": per_kind, "circuits": []}
    with open_kb(f"gates_s{seed}_k{per_kind}", taught) as e:
        before = harness.rule_set(e); before_v = harness.rule_set(e, "value")
        for kind, n in (("add8", n_adders), ("mux", n_mux)):
            for _ in range(n):
                lines, outs = adder8(W) if kind == "add8" else mux(W)
                t = time.time(); e.ingest_many(lines); t1 = time.time()
                ans = {w: e.values(f"{w} has value ?", strict=True) for w in outs}; t2 = time.time()
                right = sum(a == [v] for w, v in outs.items() for a in [ans[w]])
                wrong = sum(len(a) >= 1 and a != [v] for w, v in outs.items() for a in [ans[w]])
                res["circuits"].append({"kind": kind, "facts_ingested": len(lines), "outputs": len(outs), "right": right,
                                        "wrong": wrong, "unanswered": len(outs) - right - wrong,
                                        "ingest_s": round(t1 - t, 4), "query_s": round(t2 - t1, 4)})
        res["rules_unchanged"] = harness.rule_set(e) == before
        res["value_rules_unchanged"] = harness.rule_set(e, "value") == before_v
        res["tree_rules"] = len([r for r in before if r[0].startswith("TREE")])
    return res


# ---------- H3 / H4 machines --------------------------------------------------------------------------------------
def inc_inputs(seed):
    r = random.Random(900 + seed); out = []
    for L in range(1, 17):
        bits = ["one"] * L if L in (1, 4, 8, 16) else [r.choice(["zero", "one"]) for _ in range(L)]
        out.append(bits)
    return out


def tape_of(bits):   # most significant bit at position 0, head on the rightmost bit
    return {i: b for i, b in enumerate(bits)}, len(bits) - 1


def canon(tape, blank):
    return {k: v for k, v in sorted(tape.items()) if v != blank}


def machine_run(seed, per_transition, skip=()):
    names = tm.Names(8000 + seed * 100 + per_transition + 50 * len(skip)); rng = random.Random(seed)
    lines = tm.examples("bb3", per_transition, names, rng) + tm.examples("inc", per_transition, names, rng, skip=skip)
    res = {"seed": seed, "per_transition": per_transition, "skip": [list(s) for s in skip], "runs": []}
    with open_kb(f"tm_s{seed}_k{per_transition}{'_skip' if skip else ''}", lines) as e:
        before = harness.rule_set(e); before_s = harness.rule_set(e, "step")
        jobs = [("bb3", {}, 0)] + [("inc",) + tape_of(b) for b in inc_inputs(seed)]
        for prog, tape, head in jobs:
            got = harness.run_machine(e, prog, tape, head, names)
            t_tape, t_head, t_state, t_steps = tm.simulate(prog, tape, head, tm.START[prog])
            ok = (got["status"] == "halted" and got["steps"] == t_steps and got["head"] == t_head and
                  canon(got["tape"], tm.BLANK[prog]) == canon(t_tape, tm.BLANK[prog]))
            row = {"prog": prog, "input": [tape.get(i) for i in sorted(tape)], "status": got["status"], "steps": got["steps"],
                   "true_steps": t_steps, "correct": ok, "seconds": got["seconds"],
                   "unknown_at": {k: got[k] for k in ("at_step", "state", "symbol", "answers")} if got["status"] == "unknown" else None}
            if prog == "bb3" and ok: row["tape"] = canon(got["tape"], "zero")
            res["runs"].append(row)
        res["rules_unchanged"] = harness.rule_set(e) == before
        res["step_rules_unchanged"] = harness.rule_set(e, "step") == before_s
        res["step_rules"] = before_s
    return res


def main():
    os.makedirs(OUT, exist_ok=True); R = {}
    R["H1"] = [gates_run(s, 200) for s in SEEDS]
    for r in R["H1"]:
        c = r["circuits"]; print(f"H1 s{r['seed']}: right {sum(x['right'] for x in c)}/{sum(x['outputs'] for x in c)} "
                                 f"wrong {sum(x['wrong'] for x in c)} rules unchanged {r['rules_unchanged']} "
                                 f"ingest+query median {sorted(x['ingest_s'] + x['query_s'] for x in c)[len(c) // 2]:.3f}s", flush=True)
    GK = (2, 4, 8, 16, 32) if tm.ROUND == "1" else (2, 4, 8, 16, 32, 64, 100, 200)
    TK = (1, 2, 3, 4, 6) if tm.ROUND == "1" else (8, 16, 32, 64, 100)
    KX = 8 if tm.ROUND == "1" else 64
    R["H2_gates"] = [gates_run(s, k, n_adders=10, n_mux=20) for k in GK for s in SEEDS]
    for r in R["H2_gates"]:
        c = r["circuits"]; print(f"H2 gates k={r['per_kind']} s{r['seed']}: right {sum(x['right'] for x in c)} wrong {sum(x['wrong'] for x in c)} "
                                 f"unanswered {sum(x['unanswered'] for x in c)} of {sum(x['outputs'] for x in c)}", flush=True)
    R["H2_tm"] = [machine_run(s, k) for k in TK for s in SEEDS]
    for r in R["H2_tm"]:
        print(f"H2 tm k={r['per_transition']} s{r['seed']}: correct runs {sum(x['correct'] for x in r['runs'])}/{len(r['runs'])} "
              f"statuses {sorted(set(x['status'] for x in r['runs']))}", flush=True)
    R["H3"] = [machine_run(s, KX) for s in SEEDS]
    for r in R["H3"]:
        bb = r["runs"][0]
        print(f"H3 s{r['seed']}: bb3 {bb['status']} {bb['steps']}/{bb['true_steps']} steps correct {bb['correct']}; "
              f"inc {sum(x['correct'] for x in r['runs'][1:])}/{len(r['runs']) - 1}; rules unchanged {r['rules_unchanged']}; "
              f"bb3 {bb['seconds']}s", flush=True)
    R["H4"] = [machine_run(s, KX, skip=(("carry", "blank"),)) for s in SEEDS]
    for r in R["H4"]:
        inc = r["runs"][1:]
        ones = [x for x in inc if all(b == "one" for b in x["input"])]; other = [x for x in inc if x not in ones]
        print(f"H4 s{r['seed']}: all-ones {[(x['status'], x['unknown_at'] and x['unknown_at']['symbol']) for x in ones]}; "
              f"with a zero correct {sum(x['correct'] for x in other)}/{len(other)}", flush=True)
    json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1, default=str)
    v = verdicts(R); json.dump(v, open(os.path.join(OUT, "verdicts.json"), "w"), indent=1); print(v)


def verdicts(R):
    allc = lambda r: r["circuits"]
    v = {"H1a": all(x["right"] == x["outputs"] and x["wrong"] == 0 for r in R["H1"] for x in allc(r)),
         "H1b": all(r["rules_unchanged"] for r in R["H1"]),
         "H1b'": all(r.get("value_rules_unchanged") for r in R["H1"]),
         "H2": all(x["wrong"] == 0 for r in R["H2_gates"] for x in allc(r))
               and all(x["correct"] or x["status"] != "halted" for r in R["H2_tm"] for x in r["runs"]),
         "H3a": all(r["runs"][0]["correct"] and r["runs"][0]["true_steps"] == 14 for r in R["H3"]),
         "H3b": all(x["correct"] for r in R["H3"] for x in r["runs"][1:]),
         "H3c": all(r["rules_unchanged"] for r in R["H3"]),
         "H3c'": all(r.get("step_rules_unchanged") for r in R["H3"]),
         "H4": all((x["status"] == "unknown" and x["unknown_at"]["symbol"] == "blank") if all(b == "one" for b in x["input"]) else x["correct"]
                   for r in R["H4"] for x in r["runs"][1:])}
    return {k: "pass" if x else "fail" for k, x in v.items()}


if __name__ == "__main__":
    main()
