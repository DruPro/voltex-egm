"""Part 1 of PREREGISTRATION.md: the evolve scenario suite (unchanged) with v2.2 conditions."""
import sys, os
os.environ.setdefault("LATE", "1")
_argv = sys.argv; sys.argv = sys.argv[:1]
src = open("/home/claude/work/evolve/exp_evo.py").read()
src = src.replace('if cond in ("D", "Dx"):', 'if cond in DTYPE:').replace('    if cond in ("D", "Dx"): return', '    if cond in DTYPE: return')
exec(src.rsplit("if __name__", 1)[0])
sys.argv = _argv
V22 = "/home/claude/work/egm22/voltex2"
DTYPE = {"D", "Dx", "V22", "V22off", "V22x"}
BIN.update({"V22": V22, "V22off": V22, "V22x": V22})
PRE.update({"V22": [], "V22off": ["SET CHGREMOVALS 0", "SET SAMEFIX 0"], "V22x": ["SET DX 1"]})
E = "/home/claude/work/egm22"
for d in ("logs", "data"): os.makedirs(f"{E}/{d}", exist_ok=True)
seeds = [int(x) for x in sys.argv[1].split(",")]; conds = sys.argv[2].split(",")
out = {"runs": [], "base_only": []}
for seed in seeds:
    for wn in ["people", "database", "code"]:
        out["runs"] += run_world(wn, seed, conds)
        b = run_base_only(wn, seed, conds); out["base_only"].append({"world": wn, "seed": seed, **b})
        json.dump(out, open(os.environ["RESULTS"], "w"), indent=1)
