"""Part 2 scoring: LLM answers and EGM runs graded against the hidden key with one rule set."""
import sys, os, json, re, time, subprocess, collections, statistics as st
_argv = sys.argv; sys.argv = sys.argv[:1]
src = open("/home/claude/work/evolve/exp_evo.py").read()
exec(src.rsplit("if __name__", 1)[0])          # read(), score_probe(), cur_values(), held()
sys.argv = _argv
G = "/home/claude/work/egm22"; H = f"{G}/llm_hidden"; O = f"{G}/llm_out"
EGM_PRE = json.load(open(f"{G}/egm_config.json"))["pre"] if os.path.exists(f"{G}/egm_config.json") else []
CS = {"ch", "stale", "corr", "ooo", "db_move", "db_mgr", "db_corr", "db_ooo", "db_proj", "code_drop", "code_move", "code_ooo", "src", "db_src"}
CI = {"compat", "part2", "code_keep", "vol", "code_add"}
def klass(sc): return "change-sensitive" if sc in CS else ("change-insensitive" if sc in CI else "other")
def probe_of(k):
    t = frozenset(k["truth"]) if k["kind"] == "set" else k["truth"]
    return (k["kind"], k["rel"], k["x"], k["v"], t, k["tag"])

def norm(s): return re.sub(r"\s+", " ", str(s)).strip().strip(".").strip()
def grade_llm(k, ans):
    kind, truth = k["kind"], k["truth"]
    if ans is None: return "abstain", "missing"
    if isinstance(ans, list): vals = [norm(a).lower() for a in ans]; a_up = ""
    else:
        a = norm(ans); a_up = a.upper()
        vals = [norm(x).lower() for x in re.split(r"[,;|]| and ", a) if norm(x)]
    if kind == "conflict":
        if a_up.startswith("YES"): fl = True
        elif a_up.startswith("NO"): fl = False
        else: return "abstain", a_up
        return ("right" if fl == truth else "wrong"), ("flag" if fl else "noflag")
    if kind == "held":
        for w in ("CURRENT", "PAST", "NEVER"):
            if a_up.startswith(w): return ("right" if w.lower() == truth else "wrong"), w.lower()
        return "abstain", a_up
    if a_up in ("UNKNOWN", "CONFLICT") or (vals and vals[0].upper() in ("UNKNOWN", "CONFLICT")): return "abstain", a_up or vals[0]
    if kind == "has":
        if a_up.startswith("YES"): v = True
        elif a_up.startswith("NO"): v = False
        else: return "abstain", a_up
        return ("right" if v == truth else "wrong"), str(v)
    if kind == "set": return ("right" if set(vals) == set(x.lower() for x in truth) else "wrong"), "|".join(sorted(vals))
    if kind == "one":
        if len(vals) > 1: return "ambiguous", "|".join(vals)
        return ("right" if vals and vals[0] == str(truth).lower() else "wrong"), (vals[0] if vals else "")

def egm_rows(tag, rep):
    meta = json.load(open(f"{H}/{tag}_meta.json")); key = json.load(open(f"{H}/{tag}_key.json"))
    script = "\n".join(EGM_PRE) + ("\n" if EGM_PRE else "") + open(f"{H}/{tag}_egm_{rep}.cmds").read()
    t0 = time.time(); out = subprocess.run([f"{G}/voltex2"], input=script, capture_output=True, text=True).stdout; dt = time.time() - t0
    open(f"{G}/llm_out/egm_{rep}_{tag}.log", "w").write(out)
    facts, conf, flagged, _ = read(out, meta["preds"])
    rows = []
    for k in key:
        g, a = score_probe(probe_of(k), facts, conf, flagged, None)
        rows.append({**k, "grade": g, "ans": a})
    return rows, dt

def llm_rows(model, rep, seed):
    path = f"{O}/{model}_{rep}_s{seed}.jsonl"
    if not os.path.exists(path): return None
    ans = {}
    for l in open(path):
        l = l.strip()
        if not l: continue
        try: o = json.loads(l); ans[o["id"]] = o.get("answer")
        except Exception: pass
    rows = []
    for wn in ["people", "database", "code"]:
        for k in json.load(open(f"{H}/{wn}_s{seed}_key.json")):
            g, a = grade_llm(k, ans.get(k["id"]))
            rows.append({**k, "grade": g, "ans": a, "world": wn})
    return rows

if __name__ == "__main__":
    allrows = []
    egm_time = collections.defaultdict(float)
    for seed in [41, 42]:
        for rep in ["plain", "enriched"]:
            for wn in ["people", "database", "code"]:
                rows, dt = egm_rows(f"{wn}_s{seed}", rep); egm_time[(rep, seed)] += dt
                allrows += [{**r, "reasoner": "EGM", "rep": rep, "seed": seed, "world": wn} for r in rows]
            for model in ["sonnet", "haiku"]:
                rs = llm_rows(model, rep, seed)
                if rs is None: print(f"missing: {model} {rep} s{seed}"); continue
                allrows += [{**r, "reasoner": model, "rep": rep, "seed": seed} for r in rs]
    json.dump({"rows": allrows, "egm_seconds": {f"{k[0]}_s{k[1]}": round(v, 3) for k, v in egm_time.items()}}, open(f"{G}/results_part2.json", "w"), indent=0)
    def rate(rs, g="right"): return sum(r["grade"] == g for r in rs) / len(rs) if rs else float("nan")
    print(f"{'reasoner':8} {'rep':9} {'class':19} {'n':>4} {'right':>6} {'wrong':>6} {'ambig':>6} {'abst':>6}")
    for reasoner in ["EGM", "sonnet", "haiku"]:
        for rep in ["plain", "enriched"]:
            for cl in ["change-sensitive", "change-insensitive", "other", "history(held)", "ALL"]:
                rs = [r for r in allrows if r["reasoner"] == reasoner and r["rep"] == rep and
                      (cl == "ALL" or (cl == "history(held)" and r["kind"] == "held") or klass(r["sc"]) == cl)]
                if rs: print(f"{reasoner:8} {rep:9} {cl:19} {len(rs):4} {rate(rs):6.3f} {rate(rs, 'wrong'):6.3f} {rate(rs, 'ambiguous'):6.3f} {rate(rs, 'abstain'):6.3f}")
    print("EGM seconds:", dict(egm_time))
