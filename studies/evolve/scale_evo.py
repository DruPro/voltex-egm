"""H8 scaling: people world at scale 1/2/4 x 50/200/800 residence changes; batch (one query at the end) and
interactive (a query after every update, 50 updates). Timeout 900 s per run; a timeout is reported, never extrapolated."""
import sys, os, json, random, time, subprocess, collections
sys.argv_saved = sys.argv; sys.argv = sys.argv[:1]
exec(open("/home/claude/work/evolve/exp_evo.py").read().rsplit("if __name__", 1)[0])
sys.argv = sys.argv_saved
SEED = 21; TIMEOUT = 900
conds = ["A", "B", "C", "D", "P"]
rows = []
resf = f"{E}/results_scale.json"
def stream(scale, U):
    from world import generate, observe
    Tr, Ent = generate(SEED, scale); lines, info = observe(Tr, Ent, SEED, 0.5, n_unseen=25 * scale, n_sparse=50 * scale)
    obs = [tuple(f) for f in info["observed"]]
    rec = collections.defaultdict(list)
    for f in obs: rec[f[1]].append(f)
    ppl = sorted(x for x in rec if sum(1 for f in rec[x] if f[0] == "lives in") == 1 and x not in {e[1] for e in info["wrong"]})
    rng = random.Random(SEED * 5 + scale * 31 + U); S = Ent["settlement"]
    base = [{"src": "census", "key": x, "t": 1, "rev": 1, "scope": "snapshot", "facts": fs} for x, fs in sorted(rec.items())]
    state = {x: list(rec[x]) for x in ppl}; tnext = collections.Counter(); ups = []
    for _ in range(U):
        x = rng.choice(ppl); cur = [f for f in state[x] if f[0] == "lives in"][0]
        new = rng.choice([s for s in S if s != cur[2]]); state[x] = [f if f != cur else ("lives in", x, new) for f in state[x]]
        tnext[x] += 1; ups.append({"src": "census", "key": x, "t": 1 + tnext[x], "rev": 1, "scope": "snapshot", "facts": list(state[x])})
    return {"base": base, "one": {"lives in", "works as", "is located in", "is from"}}, ups, ppl[0]
for scale in [1, 2, 4]:
    for U in [50, 200, 800]:
        for mode in (["batch", "interactive"] if U == 50 else ["batch"]):
            wd, ups, probe_x = stream(scale, U)
            for cond in conds:
                if mode == "batch" and any(r["scale"] == scale and r["cond"] == cond and r["mode"] == "batch" and r["status"] != "ok" and r["updates"] < U for r in rows):
                    rows.append({"scale": scale, "updates": U, "mode": mode, "cond": cond, "seconds": None, "status": "timeout (implied by a smaller run's timeout)"})
                    print(f"scale {scale} U={U:4} {mode:11} {cond}: timeout implied", flush=True); continue
                bc = base_cmds(wd, cond, f"{E}/data/scale_s{scale}_base.txt")
                uc = []
                if mode == "batch": uc = translate(wd, cond, ups) + [f"ASK {probe_x} lives in ?"]
                else:
                    for i in range(len(ups)):
                        uc += translate(wd, cond, ups[: i + 1])[len(translate(wd, cond, ups[:i])):] + [f"ASK {ups[i]['key']} lives in ?"]
                script = "\n".join(PRE[cond] + bc + ["ASK " + probe_x + " lives in ?", "MARK_BASE_DONE"] + uc + ["EXIT"]) + "\n"
                t0 = time.time()
                try:
                    p = subprocess.Popen([BIN[cond]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                    # time to the end of the base (first query), then to the end of the updates
                    out, _ = p.communicate(script, timeout=TIMEOUT); total = time.time() - t0; status = "ok"
                except subprocess.TimeoutExpired:
                    p.kill(); p.communicate(); total = None; status = "timeout"
                rows.append({"scale": scale, "updates": U, "mode": mode, "cond": cond, "seconds": None if total is None else round(total, 2), "status": status,
                             "update_cmds": len(uc)})
                print(f"scale {scale} U={U:4} {mode:11} {cond}: {'>%d s (timeout)' % TIMEOUT if total is None else '%.2f s' % total}", flush=True)
                json.dump(rows, open(resf, "w"), indent=1)
# base-only cost per scale (ingest + first rebuild + one query), to separate update cost from the base build
for scale in [1, 2, 4]:
    wd, ups, probe_x = stream(scale, 1)
    for cond in conds:
        script = "\n".join(PRE[cond] + base_cmds(wd, cond, f"{E}/data/scale_s{scale}_base.txt") + [f"ASK {probe_x} lives in ?", "EXIT"]) + "\n"
        t0 = time.time(); subprocess.run([BIN[cond]], input=script, capture_output=True, text=True); total = time.time() - t0
        rows.append({"scale": scale, "updates": 0, "mode": "base_only", "cond": cond, "seconds": round(total, 2), "status": "ok"})
        print(f"scale {scale} base only {cond}: {total:.2f} s", flush=True)
        json.dump(rows, open(resf, "w"), indent=1)
