"""H1: long chains in the lineage world, CHAIN 2/3/4, 5 seeds. Scores inferred taught relations against hidden truth."""
import json, subprocess
E = "/home/claude/work/multipremise/voltex2"; out = {}
for L in (2, 3, 4):
    agg = {"gg_right": 0, "gg_unseen": 0, "ggg_right": 0, "ggg_unseen": 0, "gg_wrong": 0, "ggg_wrong": 0, "other_derived": 0}
    for s in range(5):
        T = json.load(open(f"hidden/lineage_s{s}.json"))
        txt = subprocess.run([E], input=f"SET CHAIN {L}\nINGESTFILE obs/lineage_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n", capture_output=True, text=True).stdout
        open(f"logs/h1_chain{L}_s{s}.log", "w").write(txt)
        gg, ggg = {tuple(x) for x in T["gg"]}, {tuple(x) for x in T["ggg"]}
        for l in txt.splitlines():
            if not l.startswith("FACT\t"): continue
            f = l.split("\t")[1]
            if " is great great grandparent of " in f:
                p = tuple(f.split(" is great great grandparent of ")); agg["ggg_right" if p in ggg else "ggg_wrong"] += 1
            elif " is great grandparent of " in f:
                p = tuple(f.split(" is great grandparent of ")); agg["gg_right" if p in gg else "gg_wrong"] += 1
            else: agg["other_derived"] += 1
        agg["gg_unseen"] += len(T["gg_unseen"]); agg["ggg_unseen"] += len(T["ggg_unseen"])
        if s == 0: agg["rules_seed0"] = [l.strip()[:140] for l in txt.splitlines() if l.strip().startswith("ACCEPT")]
    out[f"chain{L}"] = agg
    print(f"CHAIN {L}: great-grandparent {agg['gg_right']}/{agg['gg_unseen']} (wrong {agg['gg_wrong']}) | "
          f"great-great {agg['ggg_right']}/{agg['ggg_unseen']} (wrong {agg['ggg_wrong']}) | other derived {agg['other_derived']}")
    for r in agg["rules_seed0"]: print("    ", r)
json.dump(out, open("results_h1.json", "w"), indent=1)
