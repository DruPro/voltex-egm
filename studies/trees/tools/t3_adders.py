"""T3: 20 four-bit ripple-carry adders per seed, gate behaviour taught only on separate example gates. TREES 1 with DEPTH 0 and 4."""
import json, os, subprocess, time
E = os.environ.get("VOLTEX", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "build", "voltex2"))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
res = {}
for depth in (0, 4):
    agg = {"adders_correct": 0, "adders": 0, "wires_right": 0, "wires_wrong": 0, "wires_hidden": 0, "rounds": [], "seconds": 0}
    for s in range(5):
        T = json.load(open(f"hidden/adders_s{s}.json"))
        t0 = time.time()
        out = subprocess.run([E], input=f"SET TREES 1\nSET DEPTH {depth}\nSET PROFILE 1\nINGESTFILE obs/adders_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n", capture_output=True, text=True).stdout
        agg["seconds"] += time.time() - t0
        open(f"logs/t3_depth{depth}_s{s}.log", "w").write(out)
        got = {}
        for l in out.splitlines():
            if l.startswith("FACT\t") and " has value " in l:
                w, v = l.split("\t")[1].split(" has value "); got[w.strip()] = v.strip()
            if l.startswith("[PROFILE] infer"): agg["rounds"].append(int(l.split(",")[1].split()[0]))
        for w, v in T["hidden_wires"].items():
            agg["wires_hidden"] += 1
            if w in got: agg["wires_right" if got[w] == v else "wires_wrong"] += 1
        for ad in T["adders"]:
            agg["adders"] += 1
            bits = [got.get(w) for w in ad["outputs"]]
            if None not in bits and sum((1 if b == "one" else 0) << i for i, b in enumerate(bits)) == ad["sum"]: agg["adders_correct"] += 1
        if s == 0 and depth == 0:
            ad = T["adders"][0]; bits = [got.get(w, "?") for w in ad["outputs"]]
            agg["example"] = f"{ad['a']} + {ad['b']} = {ad['sum']}; engine's output bits (low to high): {bits}"
    res[f"depth{depth}"] = agg
    print(f"DEPTH {depth}: adders fully correct {agg['adders_correct']}/{agg['adders']} | hidden wires right {agg['wires_right']}/{agg['wires_hidden']}, wrong {agg['wires_wrong']} | rounds {sorted(set(agg['rounds']))} | {agg['seconds']:.1f}s")
print(res["depth0"].get("example"))
json.dump(res, open("results_t3.json", "w"), indent=1)
