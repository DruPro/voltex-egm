"""Performance as the world grows: scale 1,2,4,8 (500 -> 4,000 individuals), coverage 50%, seeds 0-2."""
import json, sys, time
sys.path.insert(0, "hidden")
from world import generate, observe
from evaluate import evaluate
from lib import run_voltex, oracle

rows = []
for scale in (1, 2, 4, 8):
    for seed in (0, 1, 2):
        T, E = generate(seed, scale); preds = sorted(T, key=len, reverse=True)
        lines, info = observe(T, E, seed, 0.5, n_unseen=25 * scale, n_sparse=50 * scale)
        f = f"obs/obs_scale{scale}_s{seed}.txt"; open(f, "w").write("\n".join(lines) + "\n")
        observed = [tuple(x) for x in info["observed"]]
        t = time.time(); od = oracle(observed); t_or = time.time() - t
        v = run_voltex(f, f"logs/scale{scale}_s{seed}.log", preds, True, seed=seed)
        ev = evaluate(v["derived"], observed, info, T, od, preds, v["rules"], v["conflicts"], seed)
        row = {"scale": scale, "seed": seed, "individuals": len(E["individual"]), "observations": len(lines),
               "precision": ev["precision"], "recall_derivable": ev["recall_on_derivable"], "recall_all": ev["recall"],
               "rules_accepted": ev["rules"]["accepted"], "rule_precision": ev["rules"]["rule_precision"],
               "rss_mb": v["rss_mb"], **{k: round(x, 3) for k, x in v["latency_ms"].items()}, "oracle_python_s": round(t_or, 2)}
        rows.append(row); print(row, flush=True)
json.dump(rows, open("results/scaling.json", "w"), indent=1)
