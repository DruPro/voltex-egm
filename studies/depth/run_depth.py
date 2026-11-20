"""D3: blind world, DEPTH 4 vs DEPTH 0, reusing the Blind World study's harness, hidden truth and evaluator unchanged."""
import json, os, re, sys
B = "/home/claude/work/blind"; sys.path.insert(0, B); sys.path.insert(0, B + "/hidden")
import lib
_init = lib.Voltex.__init__
DEPTH = {"v": 4}
def _patched(self, log_path):                     # send the depth setting through the normal command interface
    _init(self, log_path); self.cmd(f"SET DEPTH {DEPTH['v']}"); self.cmd("SET PROFILE 1")
lib.Voltex.__init__ = _patched
lib.BIN = "/home/claude/work/depth/voltex2"
from evaluate import evaluate
os.makedirs("logs", exist_ok=True); rows = []
for seed in range(5):
    T = json.load(open(f"{B}/hidden/truth_s{seed}.json"))["truth"]; preds = sorted(T, key=len, reverse=True)
    TRUE = {(p, a, b) for p in T for a, b in map(tuple, T[p])}
    for cov in (30, 50, 70):
        tag = f"s{seed}_c{cov}"; info = json.load(open(f"{B}/hidden/info_{tag}.json"))
        observed = [tuple(f) for f in info["observed"]]; odepth = lib.oracle(observed)
        row = {"seed": seed, "coverage": cov}
        for d in (4, 0):
            DEPTH["v"] = d
            v = lib.run_voltex(f"{B}/obs/obs_{tag}.txt", f"logs/d{d}_{tag}.log", preds, True, n_queries=0, seed=seed)
            ev = evaluate(v["derived"], observed, info, T, odepth, preds, v["rules"], v["conflicts"], seed)
            log = open(f"logs/d{d}_{tag}.log").read()
            m = re.search(r"\[PROFILE\] infer ([\d.]+) ms, (\d+) rounds", log)
            row[f"d{d}"] = {"precision": ev["precision"], "recall": ev["recall"], "derived": len(v["derived"]),
                            "wrong": sum(1 for f in v["derived"] if f not in TRUE),
                            "infer_ms": float(m.group(1)) if m else None, "rounds": int(m.group(2)) if m else None}
        rows.append(row)
        a, b = row["d4"], row["d0"]
        print(f"{tag}: depth4 P={a['precision']:.3f} R={a['recall']:.3f} derived={a['derived']} wrong={a['wrong']} | "
              f"fixpoint P={b['precision']:.3f} R={b['recall']:.3f} derived={b['derived']} wrong={b['wrong']} rounds={b['rounds']} ({b['infer_ms']} ms)", flush=True)
json.dump(rows, open("results_depth.json", "w"), indent=1)
