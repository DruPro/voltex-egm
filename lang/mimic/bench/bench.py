"""Mimic bench (PREREGISTRATION.md): every example program in every mode, against a literal reference interpreter.

  python3 lang/mimic/bench/bench.py      writes results.json and verdicts.json next to this file
"""
import json, os, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); LANG = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, LANG)
import mimic  # noqa: E402
EX = os.path.join(LANG, "examples")
PROGRAMS = ["hello", "adder", "add8", "increment", "busy_beaver", "parity", "rule110", "guess"]
MODES = ["observe", "fresh", "rebuild"]


# ------------------------------------------------------------------ reference: the tables, executed literally
def table(f): return {**f.rows, **f.hidden}


def ref_eval(p, name, args):
    if name in p.functions: return {"out": table(p.functions[name]).get(tuple(args))}
    c = p.circuits[name]; val = dict(zip(c.ins, args))
    for target, fname, a, _ in c.body:
        val[target] = table(p.functions[fname]).get(tuple(val[x] for x in a))
    return {x: val[x] for x in c.outs}


def ref_run(m, tape_text, at="end", max_steps=1000):
    t = {**m.rows, **m.hidden}; tape = {i: c for i, c in enumerate(tape_text)}
    head = len(tape_text) - 1 if at == "end" else 0 if at == "start" else int(at); q = m.start; steps = 0
    while q != "halt" and steps < max_steps:
        w, mv, n = t[(q, tape.get(head, m.blank))]; tape[head] = w; head += 1 if mv == "right" else -1; q = n; steps += 1
    return mimic.render(tape, m.blank), steps


def ref_automaton(f, width, steps, start):
    t = table(f); row = list(start); rows = ["".join(row)]
    for _ in range(steps - 1):
        row = [t[(row[(i - 1) % width], row[i], row[(i + 1) % width])] for i in range(width)]; rows.append("".join(row))
    return rows


def judge(log, p):
    """Each action -> right | wrong | unknown, against the reference."""
    out = []
    for a in log["actions"]:
        if a["kind"] == "eval":
            ref = ref_eval(p, a["program"], a["input"]); got = a["result"]
            v = "unknown" if None in got.values() else ("right" if got == ref else "wrong")
        elif a["kind"] == "run":
            m = p.machines[a["program"]]; line = [l for n, k, l in p.actions if n == a["line"]][0].split()
            ref_tape, ref_steps = ref_run(m, a["input"], at=line[line.index("at") + 1] if "at" in line else "end")
            v = "unknown" if a["status"] == "unknown" else ("right" if (a["tape"], a["steps"]) == (ref_tape, ref_steps) else "wrong")
        else:
            line = [l for n, k, l in p.actions if n == a["line"]][0].split()
            width = int(line[line.index("width") + 1]); steps = int(line[line.index("steps") + 1]); start = line[line.index("start") + 1]
            if start == "single": start = "0" * (width - 1) + "1"
            ref = ref_automaton(p.functions[a["program"]], width, steps, start)
            v = "unknown" if a["status"] == "unknown" else ("right" if a["rows"] == ref else "wrong")
        out.append({"line": a["line"], "kind": a["kind"], "program": a["program"], "verdict": v})
    return out


def run_program(name, mode):
    text = open(os.path.join(EX, name + ".mim")).read(); p = mimic.Program.parse(text)
    t = time.time(); log = mimic.execute(text, mode=mode, out=lambda s: None); dt = time.time() - t
    return {"program": name, "mode": mode, "seconds": round(dt, 2), "learn_s": log["learn_s"], "rebuilds": log["rebuilds"],
            "judged": judge(log, p), "learned": log["learned"],
            "steps_ms": [a["ms_per_step"] for a in log["actions"] if a["kind"] == "run"], "log": log}


def cost_curve():
    """B2: ms per step by mode, for increment on n ones (the carry runs the whole length)."""
    base = open(os.path.join(EX, "increment.mim")).read().split("run inc")[0]
    rows = []
    for n in (4, 8, 16, 32, 64):
        for mode in MODES:
            log = mimic.execute(base + f"run inc on {'1' * n}\n", mode=mode, out=lambda s: None)
            a = log["actions"][0]
            rows.append({"ones": n, "mode": mode, "status": a["status"], "steps": a["steps"], "ms_per_step": a["ms_per_step"],
                         "learn_s": log["learn_s"]})
    return rows


def recursive():
    """B4: add8 three ways."""
    text = open(os.path.join(EX, "add8.mim")).read(); p = mimic.Program.parse(text)
    evals = [l.split()[2:] for n, k, l in p.actions if k == "eval"]
    res = {}
    for label, depth, how in (("depth0_bottom_up", 0, "bottom"), ("depth1_bottom_up", 1, "bottom"), ("depth1_recursive", 1, "demand")):
        R = mimic.Runtime(p, mode="fresh", out=lambda s: None, depth=depth); rows = []
        for args in evals:
            q0 = R.queries; t = time.time()
            got = R.evaluate("add8", args)[0] if how == "bottom" else R.evaluate_demand("add8", args)
            ref = ref_eval(p, "add8", args)
            v = "unknown" if None in got.values() else ("right" if got == ref else "wrong")
            rows.append({"verdict": v, "unknown_outputs": sum(x is None for x in got.values()), "questions": R.queries - q0,
                         "seconds": round(time.time() - t, 3)})
        R.e.close(); R.tmp.cleanup(); res[label] = rows
    return res


def main():
    R = {"programs": [run_program(n, m) for n in PROGRAMS for m in MODES]}
    for r in R["programs"]:
        c = [j["verdict"] for j in r["judged"]]
        print(f"{r['program']:12s} {r['mode']:8s} right {c.count('right')} wrong {c.count('wrong')} unknown {c.count('unknown')} "
              f"of {len(c)}; {r['seconds']} s; ms/step {r['steps_ms']}", flush=True)
    R["determinism"] = {n: [json.dumps(run_program(n, "fresh")["judged"]) for _ in range(2)] for n in PROGRAMS}
    R["cost_curve"] = cost_curve()
    for x in R["cost_curve"]: print("cost", x, flush=True)
    R["recursive"] = recursive()
    for k, rows in R["recursive"].items():
        print("B4", k, [r["verdict"] for r in rows], "questions", [r["questions"] for r in rows], "s", [r["seconds"] for r in rows], flush=True)
    for r in R["programs"]: r.pop("log")
    json.dump(R, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=str)
    v = verdicts(R); json.dump(v, open(os.path.join(HERE, "verdicts.json"), "w"), indent=1); print(v)


def verdicts(R):
    P = R["programs"]; by = lambda mode: [j for r in P if r["mode"] == mode for j in r["judged"]]
    guess_lines = {j["line"] for r in P if r["program"] == "guess" for j in r["judged"]}
    def ok_except_guess(mode):
        return all(j["verdict"] == "right" for r in P if r["mode"] == mode and r["program"] != "guess" for j in r["judged"])
    inc_obs = [j for r in P if r["mode"] == "observe" and r["program"] == "increment" for j in r["judged"]]
    v = {"P1": all(j["verdict"] != "wrong" for m in ("fresh", "rebuild") for j in by(m)) and ok_except_guess("fresh") and ok_except_guess("rebuild"),
         "P2": all(j["verdict"] != "wrong" for j in by("observe")) and any(j["verdict"] == "unknown" for j in inc_obs),
         "P3": all(j["verdict"] != "wrong" for m in MODES for j in by(m)),
         "P4": all(r["verdict"] == "right" for r in R["recursive"]["depth1_recursive"])
               and [r["verdict"] for r in R["recursive"]["depth1_recursive"]] == [r["verdict"] for r in R["recursive"]["depth0_bottom_up"]]
               and any(r["verdict"] == "unknown" for r in R["recursive"]["depth1_bottom_up"]),
         "P5": all(a == b for a, b in R["determinism"].values())}
    return {k: "pass" if x else "fail" for k, x in v.items()}


if __name__ == "__main__":
    main()
