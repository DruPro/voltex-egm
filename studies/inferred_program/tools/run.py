"""Inferred programs: experiments X1-X5 (PREREGISTRATION.md). Writes ../results/*.json and ../results/verdicts.json.

  python3 run.py
"""
import collections, json, os, random, re, statistics, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import egm        # noqa: E402
import rulematch  # noqa: E402
OUT = os.path.join(STUDY, "results"); BIN = os.path.join(ROOT, "build", "voltex2")
TMP = tempfile.mkdtemp()
BASE = {"DEPTH": 0, "TENDENCYSTEPS": 0, "PROFILE": 1}
SLOTS = ["first", "second", "third"]


class Names:
    def __init__(self, prefix): self.p, self.n = prefix, 0
    def __call__(self): self.n += 1; return f"{self.p}{self.n}"


def gate(nm, kind, inputs, out_val=None):
    """inputs: [(wire, value or None)] -> (lines, output wire)."""
    g, o = nm(), nm(); L = [f"{o} is output of {g}", f"{g} has kind {kind}"]
    for i, (w, v) in enumerate(inputs):
        L.append(f"{g} has {SLOTS[i]} input {w}")
        if v is not None: L.append(f"{w} has value {v}")
    if out_val is not None: L.append(f"{o} has value {out_val}")
    return L, o


def engine(lines, extra=None):
    p = os.path.join(TMP, f"kb{random.random()}.txt"); open(p, "w").write("\n".join(lines) + "\n")
    words = len({w for l in lines for w in l.split()})
    return egm.open(p, settings=dict(BASE, MAXWORDS=max(12000, words + 1000), **(extra or {})), binary=BIN)


def builds(out_lines):
    full = sum("rule mining" in l for l in out_lines); refresh = sum("refresh:" in l for l in out_lines)
    return full, refresh


def output_rules(e, rel):
    return sorted((r.text, r.tier) for r in e.rules() if f"=> [? {rel} ?]" in r.text)


def facts_of(lines):
    out = []
    for l in lines:
        for rel in ("is output of", "has kind", "has first input", "has second input", "has third input", "has value",
                    "is parent of", "is child of", "is ancestor of", "next", "at", "then"):
            k = f" {rel} "
            if k in l:
                s, o = l.split(k, 1); out.append((rel, s.strip(), o.strip())); break
    return out


# ------------------------------------------------------------------ programs
FSM = {(s, b): f"s{(int(s[1]) + int(b[1])) % 3}" for s in ("s0", "s1", "s2") for b in ("b0", "b1")}


def p1_examples(nm, mixed=False):
    L = []
    for (s, b), o in FSM.items():
        for i in range(64):
            out = ("s0" if i % 2 else "s2") if (mixed and (s, b) == ("s1", "b1")) else o
            L += gate(nm, "step", [(nm(), s), (nm(), b)], out)[0]
    return L


def p1_unrolled(nm, bits, start="s0"):
    """One gate per symbol; only the start state and the symbols are stated. Returns (lines, [(wire, true state)])."""
    w = nm(); L = [f"{w} has value {start}"]; s = start; outs = []
    for b in bits:
        gl, o = gate(nm, "step", [(w, None), (nm(), b)]); L += gl
        s = FSM.get((s, b)) if s is not None else None; outs.append((o, s)); w = o
    return L, outs


def p2_world(seed=1, nodes=300, examples=150):
    r = random.Random(seed); succ = {i: r.randrange(nodes) for i in range(nodes)}
    L = [f"n{i} next n{j}" for i, j in succ.items()]
    for i in range(examples):
        k = r.randrange(nodes); L += [f"ex{i} at n{k}", f"ex{i} then n{succ[k]}"]
    return L, succ


def p3_world(seed=2, chains=40, length=12, taught=0.7):
    r = random.Random(seed); L, truth, runtime = [], [], []
    for c in range(chains):
        nodes = [f"c{c}x{k}" for k in range(length)]
        pairs = [f"{nodes[k]} is parent of {nodes[k + 1]}" for k in range(length - 1)] + \
                [f"{nodes[k + 1]} is child of {nodes[k]}" for k in range(length - 1)]
        anc = [f"{nodes[i]} is ancestor of {nodes[j]}" for i in range(length) for j in range(i + 1, length)]
        if r.random() < taught: L += pairs + anc
        else: runtime += pairs; truth += anc
    return L, runtime, truth


def p4_world(nm, adders=10, seed=3):
    r = random.Random(seed); OPS = {"and": lambda a, b: a & b, "or": lambda a, b: a | b, "xor": lambda a, b: a ^ b}
    V = {0: "zero", 1: "one"}; L = []
    for k, f in OPS.items():
        for _ in range(200):
            a, b = r.randint(0, 1), r.randint(0, 1); L += gate(nm, k, [(nm(), V[a]), (nm(), V[b])], V[f(a, b)])[0]
    R, outs = [], []
    for _ in range(adders):
        cw, cv = nm(), 0; R.append(f"{cw} has value zero")
        for i in range(8):
            a, b = r.randint(0, 1), r.randint(0, 1); aw, bw = nm(), nm(); R += [f"{aw} has value {V[a]}", f"{bw} has value {V[b]}"]
            g1, t = gate(nm, "xor", [(aw, None), (bw, None)]); g2, s = gate(nm, "xor", [(t, None), (cw, None)])
            g3, u = gate(nm, "and", [(aw, None), (bw, None)]); g4, v = gate(nm, "and", [(t, None), (cw, None)])
            g5, c2 = gate(nm, "or", [(u, None), (v, None)]); R += g1 + g2 + g3 + g4 + g5
            outs.append((s, V[a ^ b ^ cv])); cv = (a & b) | ((a ^ b) & cv); cw = c2
        outs.append((cw, V[cv]))
    return L, R, outs


R110 = {(1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0, (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0}


def p5_world(nm, width=32, steps=16, seed=4):
    r = random.Random(seed); V = {0: "zero", 1: "one"}; L = []
    for (a, b, c), o in R110.items():
        for _ in range(64): L += gate(nm, "rule110", [(nm(), V[a]), (nm(), V[b]), (nm(), V[c])], V[o])[0]
    row = [0] * (width - 1) + [1]; wires = [nm() for _ in range(width)]
    R = [f"{w} has value {V[x]}" for w, x in zip(wires, row)]; outs = []
    for _ in range(steps - 1):
        nrow = [R110[(row[(i - 1) % width], row[i], row[(i + 1) % width])] for i in range(width)]; nw = []
        for i in range(width):
            gl, o = gate(nm, "rule110", [(wires[(i - 1) % width], None), (wires[i], None), (wires[(i + 1) % width], None)])
            R += gl; nw.append(o); outs.append((o, V[nrow[i]]))
        row, wires = nrow, nw
    return L, R, outs


# ------------------------------------------------------------------ X1: one pass
def x1_case(name, taught, runtime, outs, rel="has value", extra=None):
    with engine(taught, extra) as e0: r0 = output_rules(e0, rel)
    with engine(taught + runtime, extra) as e:
        out = e.cmd("RELATIONS"); full, refresh = builds(out)
        stated = set(taught + runtime); right = wrong = unknown = 0; derived_stated = 0; later_builds = 0; answers = []
        for w, v in outs:
            q = f"{w} {rel} ?" if rel == "has value" else w
            got = e.cmd(f"ASK {q}"); later_builds += builds(got)[0]
            fs = [f for f in e.ask(q, strict=True) if f.status != "stated"] if rel == "has value" else None
            if rel == "has value":
                vals = sorted({f.object for f in fs})
                if vals == [v]: right += 1
                elif vals: wrong += 1
                else: unknown += 1
                derived_stated += any(f"{w} has value {x}" in stated for x in vals)
                if fs: answers.append(fs[0].fact)
        r1 = output_rules(e, rel)
        prov = provenance(e, taught, answers[:40])
    return {"program": name, "items": len(outs), "right": right, "wrong": wrong, "unknown": unknown,
            "derived_stated": derived_stated, "full_builds_first": full, "builds_after_first": later_builds,
            "output_rules_identical": r0 == r1, "output_rules": len(r1), "provenance": prov}


def x1_recursion():
    taught, runtime, truth = p3_world()
    with engine(taught) as e0: r0 = output_rules(e0, "is ancestor of")
    with engine(taught + runtime) as e:
        full, _ = builds(e.cmd("RELATIONS"))
        got = {" ".join(f.fact.split()) for f in e.infer_all() if f.relation == "is ancestor of" and f.status != "stated"}
        t = set(truth); r1 = output_rules(e, "is ancestor of")
        prov = provenance(e, taught, sorted(got & t)[:40])
    return {"program": "P3 recursion", "items": len(t), "right": len(got & t), "wrong": len(got - t), "unknown": len(t - got),
            "derived_stated": len(got & set(taught + runtime)), "full_builds_first": full, "builds_after_first": 0,
            "output_rules_identical": r0 == r1, "output_rules": len(r1), "provenance": prov}


# ------------------------------------------------------------------ X4: provenance
def provenance(e, taught, answers):
    """(a) each answer's proof reaches stated facts; (b) each rule used has supporting examples among the taught facts;
    (c) the recovered support count equals the engine's k."""
    idx = rulematch.index(facts_of(taught)); rules = {r.text: r for r in e.rules()}
    seen_rules, a_ok, b_ok, c_ok, c_bad = {}, 0, 0, 0, []
    for fact in answers:
        ok, used = proof_reaches_stated(e, fact)
        a_ok += ok
        for rt in used:
            if rt in seen_rules: continue
            n, k, ex = rulematch.support(rt, idx); r = rules.get(rt)
            seen_rules[rt] = {"n": n, "k": k, "engine_k": r.k if r else None, "engine_n": r.n if r else None, "examples": ex[:3]}
    for rt, s in seen_rules.items():
        b_ok += s["k"] > 0
        if s["k"] == s["engine_k"]: c_ok += 1
        else: c_bad.append({"rule": rt, **{k: v for k, v in s.items() if k != "examples"}})
    return {"answers_checked": len(answers), "proof_reaches_stated": a_ok, "rules_used": len(seen_rules),
            "rules_with_examples": b_ok, "support_count_matches_engine": c_ok, "mismatches": c_bad[:5],
            "example_trace": next(iter(seen_rules.items()), None)}


def proof_reaches_stated(e, fact, seen=None, used=None):
    seen = set() if seen is None else seen; used = set() if used is None else used
    if fact in seen: return True, used
    seen.add(fact)
    for f in e.ask(fact.rsplit(" ", 1)[0] + " ?"):
        if " ".join(f.fact.split()) != " ".join(fact.split()): continue
        if f.status == "stated": return True, used
        if not f.because: return False, used
        used.add(f.rule)
        return all(proof_reaches_stated(e, b, seen, used)[0] for b in f.because), used
    return False, used


# ------------------------------------------------------------------ X2 / X3: across passes
def loop_p2(refresh, steps=200):
    L, succ = p2_world(); L.append("run at n0")
    with engine(L, {"REFRESH": refresh}) as e:
        e.cmd("RELATIONS"); pos, ok, full, ref, ts = 0, 0, 0, 0, []
        for _ in range(steps):
            t = time.time(); out = e.cmd(f"ASK run then ?"); f, r = builds(out); full += f; ref += r
            got = [x.object for x in e.ask("run then ?") if x.status != "stated"]
            ok += got == [f"n{succ[pos]}"]
            e.retract(f"run at n{pos}"); pos = succ[pos]; e.ingest(f"run at n{pos}"); ts.append(time.time() - t)
    return {"program": "P2 pointer walk", "refresh": refresh, "steps": steps, "right": ok, "full_builds": full,
            "refresh_builds": ref, "ms_per_step": round(1000 * statistics.median(ts), 2)}


def loop_p1(refresh, bits):
    nm = Names("q"); L = p1_examples(nm)
    W, X = nm(), nm(); gl, O = gate(nm, "step", [(W, None), (X, None)])
    s = "s0"; cur = [f"{W} has value {s}", f"{X} has value {bits[0]}"]
    with engine(L + gl + cur, {"REFRESH": refresh, "TREES": 1}) as e:
        e.cmd("RELATIONS"); ok, full, ref, ts = 0, 0, 0, []
        for i, b in enumerate(bits):
            t = time.time()
            if i:
                for f in cur: e.retract(f)
                cur = [f"{W} has value {s}", f"{X} has value {b}"]; e.ingest_many(cur)
            out = e.cmd(f"ASK {O} has value ?"); f, r = builds(out); full += f; ref += r
            got = sorted({x.object for x in e.ask(f"{O} has value ?", strict=True) if x.status != "stated"})
            truth = FSM[(s, b)]; ok += got == [truth]; ts.append(time.time() - t)
            if got != [truth]: break
            s = truth
    return {"program": "P1 state machine (loop)", "refresh": refresh, "steps": len(ts), "right": ok, "full_builds": full,
            "refresh_builds": ref, "ms_per_step": round(1000 * statistics.median(ts), 2)}


def chunked_p1(bits, K):
    """X3: K steps unrolled per pass; the last state is carried into the next pass."""
    s, ok, t0, passes = "s0", 0, time.time(), 0
    nm0 = Names("t"); L = p1_examples(nm0)
    for c in range(0, len(bits), K):
        nm = Names(f"k{c}x"); RL, outs = p1_unrolled(nm, bits[c:c + K], start=s)
        with engine(L + RL, {"TREES": 1}) as e:
            passes += 1
            for w, v in outs:
                got = sorted({x.object for x in e.ask(f"{w} has value ?", strict=True) if x.status != "stated"})
                ok += got == [v]
            s = outs[-1][1]
    dt = time.time() - t0
    return {"K": K, "steps": len(bits), "right": ok, "passes": passes, "ms_per_step": round(1000 * dt / len(bits), 2)}


# ------------------------------------------------------------------ X5: failure
def x5():
    res = {}
    def run_bits(nm, L, bits, start="s0"):
        RL, outs = p1_unrolled(nm, bits, start=start)
        with engine(L + RL, {"TREES": 1}) as e:
            rows = []
            for w, v in outs:
                fs = [x for x in e.ask(f"{w} has value ?") if x.status != "stated"]
                law = sorted({x.object for x in fs if x.tier == "law"}); tend = sorted({x.object for x in fs if x.tier != "law"})
                rows.append({"truth": v, "law": law, "tendency": tend})
        return rows
    r = random.Random(9)
    nm = Names("u"); L = p1_examples(nm)
    bits = [r.choice(["b0", "b1"]) for _ in range(30)]; bad = bits[:12] + ["b2"] + bits[13:]
    res["a_untaught_symbol"] = run_bits(nm, L, bad)
    nm = Names("v"); L = p1_examples(nm, mixed=True)
    res["b_mixed_transition"] = run_bits(nm, L, bits)
    nm = Names("w"); L = p1_examples(nm)
    res["c_untaught_state"] = run_bits(nm, L, bits, start="s3")
    return res


def main():
    os.makedirs(OUT, exist_ok=True); R = {}
    r = random.Random(5); strings = [[r.choice(["b0", "b1"]) for _ in range(64)] for _ in range(20)]
    R["X1"] = [x1_case("P1 state machine (unrolled)", p1_examples(Names("p")), *zip_runtime(strings), extra={"TREES": 1})]
    R["X1"].append(x1_recursion())
    nm = Names("m"); L, RL, outs = p4_world(nm); R["X1"].append(x1_case("P4 8-bit adders", L, RL, outs, extra={"TREES": 1}))
    nm = Names("r"); L, RL, outs = p5_world(nm); R["X1"].append(x1_case("P5 Rule 110", L, RL, outs, extra={"TREES": 1}))
    for x in R["X1"]: print("X1", {k: v for k, v in x.items() if k != "provenance"}, "| prov", {k: v for k, v in x["provenance"].items() if k in ("answers_checked", "proof_reaches_stated", "rules_used", "rules_with_examples", "support_count_matches_engine")}, flush=True)
    bits64 = strings[0]
    R["X2"] = [loop_p2(0.05), loop_p2(0), loop_p1(0.05, bits64), loop_p1(0, bits64)]
    for x in R["X2"]: print("X2", x, flush=True)
    bits256 = [r.choice(["b0", "b1"]) for _ in range(256)]
    R["X3"] = [chunked_p1(bits256, K) for K in (1, 8, 32, 256)]
    for x in R["X3"]: print("X3", x, flush=True)
    R["X5"] = x5()
    for k, rows in R["X5"].items():
        wrong_law = sum(1 for x in rows if x["law"] and x["law"] != [x["truth"]])
        first_unknown = next((i for i, x in enumerate(rows) if not x["law"]), None)
        print("X5", k, "wrong law", wrong_law, "first step without a law answer", first_unknown, flush=True)
    json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1, default=str)


def zip_runtime(strings):
    nm = Names("p"); nm.n = 10_000_000   # runtime names disjoint from the example names
    RL, outs = [], []
    for bits in strings:
        a, b = p1_unrolled(nm, bits); RL += a; outs += b
    return RL, outs


if __name__ == "__main__":
    main()
