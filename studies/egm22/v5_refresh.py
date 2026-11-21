"""V5: refresh (reuse classes and rules for small changes) - timing and answer identity against full rebuild."""
import sys, os, json, time, subprocess, collections
os.environ["LATE"] = "1"
_argv = sys.argv; sys.argv = sys.argv[:1]
exec(open("/home/claude/work/evolve/exp_evo.py").read().rsplit("if __name__", 1)[0])
src = open("/home/claude/work/evolve/scale_evo.py").read(); exec(src.split("for scale in [1, 2, 4]:")[0].split("SEED = 21")[1].join(["SEED = 21", ""]) if False else src.split("for scale in [1, 2, 4]:")[0])
sys.argv = _argv
V22 = "/home/claude/work/egm22/voltex2"; G = "/home/claude/work/egm22"
res = {"timing": [], "identity": []}
def obs_cmd(o): return f"OBSERVE {o['src']} {o['key']} {o['t']} {o['rev']} {o['scope']} | " + " ; ".join(T(f) for f in o["facts"])
# (a) timing: scale 4, 50 updates, query after each
for scale in [1, 2, 4]:
    wd, ups, px = stream(scale, 50)
    base = [obs_cmd(o) for o in wd["base"]]
    for refresh in [0, 0.02]:
        cmds = [f"SET REFRESH {refresh}"] + base + [f"ASK {px} lives in ?"]
        for u in ups: cmds += [obs_cmd(u), f"ASK {u['key']} lives in ?"]
        cmds += ["BUILDS", "EXIT"]
        t0 = time.time(); out = subprocess.run([V22], input="\n".join(cmds) + "\n", capture_output=True, text=True).stdout; dt = time.time() - t0
        b = [l for l in out.splitlines() if l.startswith("[BUILDS]")][0]
        res["timing"].append({"scale": scale, "refresh": refresh, "seconds": round(dt, 2), "builds": b})
        print(f"timing scale {scale} refresh {refresh}: {dt:.2f} s  {b}", flush=True)
        json.dump(res, open(f"{G}/results_v5.json", "w"), indent=1)
# (b) identity: people-world scenario sessions, a query after every observation, refresh vs full
for seed in [31, 32, 33, 34, 35]:
    full = WORLDS["people"](seed)
    for sc in dict.fromkeys(i["sc"] for i in full["inst"]):
        inst = [i for i in full["inst"] if i["sc"] == sc]
        rounds = max(len(i["obs"]) for i in inst)
        arrivals = [i["obs"][r] for r in range(rounds) for i in inst if r < len(i["obs"])]
        rels = sorted({p[1] for i in inst for p in i["probes"] if p[1] != "*"})
        outs = {}
        for refresh in [0, 0.02]:
            cmds = [f"SET REFRESH {refresh}"] + [obs_cmd(o) for o in full["base"]] + ["ASK __mark__ lives in ?"]
            for o in arrivals: cmds += [obs_cmd(o)] + [f"ASK {o['key']} {r} ?" for r in rels] + ["FIND __sep__"]
            cmds += ["CONFLICTS"] + [f"ASK ? {r} ?" for r in rels] + ["BUILDS", "EXIT"]
            outs[refresh] = subprocess.run([V22], input="\n".join(cmds) + "\n", capture_output=True, text=True).stdout
        def blocks(out):   # answers after each observation, then the final answers
            body = [l for l in out.splitlines() if not l.startswith("[OBSERVE]") and not l.startswith("[SET]") and not l.startswith("[BUILDS]")]
            txt = "\n".join(body); parts = txt.split("[FIND]") if "[FIND]" in txt else txt.split("\n\n")
            return parts
        a, b = blocks(outs[0]), blocks(outs[0.02])
        same = sum(x == y for x, y in zip(a, b)); n = max(len(a), len(b))
        bl = [l for l in outs[0.02].splitlines() if l.startswith("[BUILDS]")][0]
        res["identity"].append({"seed": seed, "session": sc, "blocks": n, "identical": same, "builds_refresh_run": bl})
        print(f"identity s{seed} {sc:8} {same}/{n}  {bl}", flush=True)
        json.dump(res, open(f"{G}/results_v5.json", "w"), indent=1)
tot = sum(r["blocks"] for r in res["identity"]); same = sum(r["identical"] for r in res["identity"])
print(f"V5 identity: {same}/{tot} = {same / tot:.4f}")
