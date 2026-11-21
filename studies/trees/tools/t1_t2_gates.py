"""T1/T2: gate world (xor, and, or, nand + decoy rnd), 5 seeds, TREES 0 vs 1. Scores hidden outputs."""
import json, os, subprocess, sys, time
E = os.environ.get("VOLTEX", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "build", "voltex2"))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
res = {}
for trees in (0, 1):
    agg = {"real_right": 0, "real_wrong": 0, "real_hidden": 0, "rnd_inferred": 0, "rnd_hidden": 0, "rnd_rules": 0, "rules": 0, "seconds": 0}
    for s in range(5):
        H = json.load(open(f"hidden/gates_s{s}.json"))["hidden_outputs"]
        t0 = time.time()
        out = subprocess.run([E], input=f"SET TREES {trees}\nINGESTFILE obs/gates_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n", capture_output=True, text=True).stdout
        agg["seconds"] += time.time() - t0
        open(f"logs/t1_trees{trees}_s{s}.log", "w").write(out)
        got = {}
        for l in out.splitlines():
            if l.startswith("FACT\t") and " has value " in l:
                w, v = l.split("\t")[1].split(" has value "); got[w.strip()] = v.strip()
        for w, h in H.items():
            if h["kind"] == "rnd":
                agg["rnd_hidden"] += 1; agg["rnd_inferred"] += w in got
            else:
                agg["real_hidden"] += 1
                if w in got: agg["real_right" if got[w] == h["value"] else "real_wrong"] += 1
        acc = [l.strip() for l in out.splitlines() if l.strip().startswith("ACCEPT TREE")]
        agg["rules"] += len(acc); agg["rnd_rules"] += sum("rnd)" in a for a in acc)
        if s == 0: agg["rules_seed0"] = [a[:200] for a in acc]
    res[f"trees{trees}"] = agg
    print(f"TREES {trees}: real gates {agg['real_right']}/{agg['real_hidden']} right, {agg['real_wrong']} wrong | "
          f"rnd gates inferred {agg['rnd_inferred']}/{agg['rnd_hidden']} | tree rules {agg['rules']} (naming rnd: {agg['rnd_rules']}) | {agg['seconds']:.1f}s")
for r in res["trees1"]["rules_seed0"]: print("   ", r)
json.dump(res, open("results_t1_t2.json", "w"), indent=1)
