"""Main experiment: 5 seeds x 3 coverage levels x 4 systems. Writes obs/ (what Voltex sees), logs/, results/."""
import json, os, sys, time
sys.path.insert(0, "hidden")
from world import generate, observe
from evaluate import evaluate
from lib import run_voltex, graph_baseline, oracle

SEEDS = [0, 1, 2, 3, 4]; COVERAGES = [0.3, 0.5, 0.7]
os.makedirs("obs", exist_ok=True); os.makedirs("logs", exist_ok=True); os.makedirs("results", exist_ok=True)
all_rows = []
for seed in SEEDS:
    T, E = generate(seed)
    preds = sorted(T, key=len, reverse=True)
    json.dump({"truth": T, "entities": E}, open(f"hidden/truth_s{seed}.json", "w"))
    for cov in COVERAGES:
        tag = f"s{seed}_c{int(cov * 100)}"
        lines, info = observe(T, E, seed, cov)
        open(f"obs/obs_{tag}.txt", "w").write("\n".join(lines) + "\n")       # the ONLY thing Voltex receives
        json.dump(info, open(f"hidden/info_{tag}.json", "w"))
        observed = [tuple(f) for f in info["observed"]]
        odepth = oracle(observed)
        row = {"seed": seed, "coverage": cov, "observations": len(lines)}
        t0 = time.time()
        von = run_voltex(f"obs/obs_{tag}.txt", f"logs/voltex_on_{tag}.log", preds, True, seed=seed)
        row["voltex_on"] = evaluate(von["derived"], observed, info, T, odepth, preds, von["rules"], von["conflicts"], seed)
        row["voltex_on"]["latency_ms"] = von["latency_ms"]; row["voltex_on"]["rss_mb"] = von["rss_mb"]
        row["voltex_on"]["unparsed_derived"] = von["unparsed_derived"]; row["voltex_on"]["templates"] = von["templates"]
        voff = run_voltex(f"obs/obs_{tag}.txt", f"logs/voltex_off_{tag}.log", preds, False, n_queries=20, seed=seed)
        row["voltex_off"] = evaluate(voff["derived"], observed, info, T, odepth, preds, voff["rules"], voff["conflicts"], seed)
        row["graph"] = evaluate(graph_baseline(observed, preds), observed, info, T, odepth, preds, seed=seed)
        row["oracle"] = evaluate(set(odepth), observed, info, T, odepth, preds, seed=seed)
        all_rows.append(row)
        v = row["voltex_on"]
        print(f"{tag}: obs={len(lines)} | voltex P={v['precision']} R={v['recall']:.3f} Rd={v['recall_on_derivable']:.3f} "
              f"rules {v['rules']['accepted']} valid {v['rules']['valid(true_conf>=0.9)']} | graph P={row['graph']['precision']} "
              f"| oracle P={row['oracle']['precision']:.3f} R={row['oracle']['recall']:.3f} | {time.time() - t0:.1f}s", flush=True)
json.dump(all_rows, open("results/main_runs.json", "w"), indent=1, default=str)
