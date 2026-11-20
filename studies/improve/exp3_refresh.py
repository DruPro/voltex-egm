"""Exp 3b: deferred refresh. Ingest 90% of a dataset, then stream the last 10% one fact at a time with an ASK after each.
Compare per-cycle latency and final accuracy: full rebuild every time (current) vs REFRESH 0.1 (re-mine after 10% growth)."""
import subprocess, time, random, statistics as st, json
from harness import *
out_rows = []
for scale, seeds in ((1, (0, 1, 2)), (8, (0,))):
    for seed in seeds:
        T, E = generate(seed, scale); lines, info = observe(T, E, seed, 0.5, n_unseen=25 * scale, n_sparse=50 * scale)
        r = random.Random(seed); r.shuffle(lines)
        cut = int(0.9 * len(lines)); base = f"{DATA}/base_{scale}_{seed}.txt"; open(base, "w").write("\n".join(lines[:cut]) + "\n")
        stream = lines[cut:][: (300 if scale == 1 else 60)]
        preds = sorted(T, key=len, reverse=True); observed = [tuple(f) for f in info["observed"]]
        for name, sets in (("full rebuild", ["COV 2"]), ("refresh 10%", ["COV 2", "REFRESH 0.1"])):
            p = subprocess.Popen(["stdbuf", "-oL", EXP], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
            def cmd(c):
                p.stdin.write(c + "\nFIND __m__\n"); p.stdin.flush(); o = []
                while True:
                    l = p.stdout.readline()
                    if l.startswith("[FIND] not stored"): return o
                    o.append(l)
            for s_ in sets: cmd(f"SET {s_}")
            cmd(f"INGESTFILE {base}"); cmd("INFER")
            lat = []
            for f in stream:
                t = time.perf_counter(); cmd(f"INGEST {f}"); cmd(f"ASK {f.split()[0]} is from ?"); lat.append((time.perf_counter() - t) * 1000)
            fin = cmd("INFER ALL"); cmd("RELATIONS")
            derived = {parse_fact(l.split("\t")[1], preds) for l in fin if l.startswith("FACT\t")} - {None}
            p.stdin.write("EXIT\n"); p.stdin.flush(); p.wait()
            # score against truth using only what was ingested (base + stream)
            seen = set(lines[:cut] + stream); obs_now = [f for f in observed if f"{f[1]} {f[0]} {f[2]}" in seen]
            ev = evaluate(derived, obs_now, info, T, oracle(obs_now), preds, seed=seed)
            row = {"scale": scale, "seed": seed, "policy": name, "cycle_ms_mean": st.mean(lat), "cycle_ms_p95": sorted(lat)[int(0.95 * len(lat)) - 1],
                   "precision": ev["precision"], "recall": ev["recall"], "recall_derivable": ev["recall_on_derivable"]}
            out_rows.append(row); print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
json.dump(out_rows, open("results_exp3b.json", "w"), indent=1)
