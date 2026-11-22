"""Run every world x seed x configuration, score against complete truth, and compute the pre-registered verdicts.

  python3 run.py            writes ../results/<world>_s<seed>__<config>.json and ../results/verdicts.json
  python3 run.py verdicts   recomputes ../results/verdicts.json from the results files only
"""
import collections, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
OBS = os.path.join(STUDY, "obs"); OUT = os.path.join(STUDY, "results"); BIN = os.path.join(ROOT, "build", "voltex2")
CONFIGS = {"trees_depth0": {"TREES": 1, "DEPTH": 0}, "trees_depth4": {"TREES": 1}, "notrees": {}}
# exploratory, added after seeing mixed_s1 (DEVIATIONS.md 1): law-tier proofs only. Not part of the verdicts.
EXPLORATORY = {"trees_depth0_lawonly": {"TREES": 1, "DEPTH": 0, "TENDENCYSTEPS": 0}}
WORLDS = ["nand", "mixed", "rule110", "rnd"]


def kind_of(circuit):
    """xor_3 -> xor, add8_0 -> add8, automaton -> automaton, single_rnd_212 -> single."""
    if circuit is None: return "?"
    if circuit.startswith("single"): return "single"
    return circuit if circuit == "automaton" else circuit.rsplit("_", 1)[0]


def run(world, seed, cfg):
    settings = CONFIGS.get(cfg) or EXPLORATORY[cfg]
    name = f"{world}_s{seed}"; t = json.load(open(os.path.join(OBS, name + ".truth.json")))
    hidden, depth, circ = t["hidden"], t["depth"], t["circuit"]
    t0 = time.time()
    with egm.open(os.path.join(OBS, name + ".txt"), settings=settings, binary=BIN) as e:
        facts = e.infer_all(); t1 = time.time()
        rnd = {c["fact"]: c.get("round") for c in e.chains()}
        rules = [{"text": r.text, "tier": r.tier, "known": r.known, "agree": r.agree} for r in e.rules()]
        got = collections.defaultdict(list)
        for f in facts:
            if f.relation == "has value" and f.subject in hidden and f.status != "stated":
                got[f.subject].append((f.object, f.tier, rnd.get(f.fact)))
        ok = sorted((w for w in hidden if len(got.get(w, [])) == 1 and got[w][0][0] == hidden[w]), key=lambda w: depth[w])
        sample = None
        if ok:   # one correct answer's proof, at the median depth of the correct answers
            w = ok[len(ok) // 2]
            sample = {"wire": w, "gate_depth": depth[w], "circuit": circ[w],
                      "answers": [{"fact": f.fact, "tier": f.tier, "rule": f.rule, "because": f.because}
                                  for f in e.ask(f"{w} has value ?") if f.status != "stated"]}
    state = {}
    for w, v in hidden.items():
        g = got.get(w, [])
        if not g: state[w] = ("unanswered", None, None)
        elif len({o for o, _, _ in g}) > 1: state[w] = ("wrong", "conflicting", None)
        else: state[w] = ("correct" if g[0][0] == v else "wrong", g[0][1], g[0][2])
    c = collections.Counter(s for s, _, _ in state.values())
    tiers = collections.Counter(f"{tr} {s}" for s, tr, _ in state.values() if tr)
    wires = collections.defaultdict(collections.Counter); circuits = collections.defaultdict(list)
    for w, (s, _, _) in state.items():
        wires[kind_of(circ[w])][s] += 1
        circuits[circ[w]].append(s == "correct")
    full = collections.defaultdict(lambda: [0, 0])
    for cid, oks in circuits.items():
        if kind_of(cid) == "single": continue   # single gates are scored per wire
        full[kind_of(cid)][0] += all(oks); full[kind_of(cid)][1] += 1
    rounds = collections.defaultdict(int)
    for w, (s, _, r) in state.items():
        if s == "correct" and r is not None: rounds[depth[w]] = max(rounds[depth[w]], r)
    res = {"world": world, "seed": seed, "config": cfg, "settings": settings, "exploratory": cfg in EXPLORATORY, "hidden": len(hidden),
           "correct": c["correct"], "wrong": c["wrong"], "unanswered": c["unanswered"], "tiers": dict(tiers),
           "wires_by_kind": {k: dict(v) for k, v in wires.items()}, "circuits_fully_correct": dict(full),
           "max_gate_depth_correct": max((depth[w] for w, (s, _, _) in state.items() if s == "correct"), default=0),
           "max_round_by_gate_depth": dict(sorted(rounds.items())), "build_and_infer_s": round(t1 - t0, 2),
           "tree_rules": [r for r in rules if "TREE" in r["text"]], "proof_sample": sample}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, f"{name}__{cfg}.json"), "w"), indent=1, default=str)
    return res


def verdicts(R):
    g = lambda w, cfg: [r for r in R if r["world"] == w and r["config"] == cfg]
    def circ_frac(r, kinds):
        a = sum(r["circuits_fully_correct"].get(k, [0, 0])[0] for k in kinds)
        return a / max(1, sum(r["circuits_fully_correct"].get(k, [0, 0])[1] for k in kinds))
    wk = lambda r, k, s: r["wires_by_kind"].get(k, {}).get(s, 0)
    v = {"C1": all(circ_frac(r, ["xor", "fulladd", "add4"]) >= 0.95 and r["wrong"] == 0 for r in g("nand", "trees_depth0")),
         "C2": all(circ_frac(r, ["add8", "mux"]) >= 0.95 and r["wrong"] == 0 for r in g("mixed", "trees_depth0")),
         "C3": all(wk(r, "single", "correct") >= 0.95 * 60 and wk(r, "single", "wrong") == 0 for r in g("rule110", "trees_depth0")),
         "C4": all(wk(r, "automaton", "correct") >= 0.95 * 240 and wk(r, "automaton", "wrong") == 0 for r in g("rule110", "trees_depth0")),
         "C5": all(a["correct"] <= b["correct"] and a["wrong"] == 0
                   for w in WORLDS for a, b in zip(sorted(g(w, "trees_depth4"), key=lambda r: r["seed"]),
                                                   sorted(g(w, "trees_depth0"), key=lambda r: r["seed"]))),
         "C6": all(r["correct"] + r["wrong"] == 0 for w in WORLDS for r in g(w, "notrees"))
               and all(r["tiers"].get("law correct", 0) + r["tiers"].get("law wrong", 0) == 0
                       for r in g("rnd", "trees_depth0") + g("rnd", "trees_depth4")),
         "C7": all(r["build_and_infer_s"] < 120 for r in R)}
    return {k: "pass" if x else "fail" for k, x in v.items()}


def main():
    if sys.argv[1:] == ["verdicts"]:
        R = [json.load(open(os.path.join(OUT, f))) for f in sorted(os.listdir(OUT)) if "__" in f]
        R = [r for r in R if not r.get("exploratory")]
    elif sys.argv[1:] == ["exploratory"]:
        for w in WORLDS:
            for s in range(3):
                for cfg in EXPLORATORY:
                    r = run(w, s, cfg)
                    print(f"{w}_s{s} {cfg} correct {r['correct']}/{r['hidden']} wrong {r['wrong']} unanswered {r['unanswered']} "
                          f"circuits {r['circuits_fully_correct']} tiers {r['tiers']} {r['build_and_infer_s']}s", flush=True)
        return
    else:
        R = []
        for w in WORLDS:
            for s in range(3):
                for cfg in CONFIGS:
                    r = run(w, s, cfg); R.append(r)
                    print(f"{w}_s{s} {cfg:13s} correct {r['correct']}/{r['hidden']} wrong {r['wrong']} "
                          f"unanswered {r['unanswered']} circuits {r['circuits_fully_correct']} "
                          f"depth {r['max_gate_depth_correct']} {r['build_and_infer_s']}s", flush=True)
    v = verdicts(R); json.dump(v, open(os.path.join(OUT, "verdicts.json"), "w"), indent=1); print(v)


if __name__ == "__main__":
    main()
