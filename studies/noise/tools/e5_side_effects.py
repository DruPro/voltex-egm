"""E5 side effects of each new switch on noise-free data. Writes results_side_effects.json.
  gate datasets: does the output change at all (same body as the equivalence gate)?
  tree gates (studies/trees T1), adders (T3), lineage CHAIN 3, harvest CONDITIONS 1: correct and wrong inferences."""
import glob, json, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import worlds  # noqa: E402

SW = {"off": [], "REPLICATE": ["SET REPLICATE 1"], "QUARANTINE": ["SET QUARANTINE 1"], "VOTE": ["SET VOTE 1"]}
WORK = "/home/claude/work"
GATE = sorted(glob.glob(f"{WORK}/blind/obs/obs_s*_c*.txt")) + [f"{WORK}/complex/{d}/facts.txt" for d in ("clean", "noisy", "noisy15")] + \
    [f"{WORK}/code/data/code_facts.txt", f"{WORK}/explain/facts.txt", f"{WORK}/v2/data/world_train.txt", f"{WORK}/scale_econ/corpus/M.txt"]
BODY = "INGESTFILE {f}\nRELATIONS\nINFER ALL\nINFER\nCONFLICTS\nCLASSES\nASK ? is from ?\nASK ? is located in ?\nASK ? lives in ?\nINFER ALL\nEXIT\n"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_side_effects.json")


def eng(cmds):
    return subprocess.run([lib.VOLTEX], input=cmds, capture_output=True, text=True).stdout


def strip(o):
    return "\n".join(l for l in o.splitlines() if "MB/s" not in l and not l.startswith(("[CONFIG]", "[SET]")))


def facts(o, rel):
    return {tuple(l.split("\t")[1].split(f" {rel} ")) for l in o.splitlines() if l.startswith("FACT\t") and f" {rel} " in l}


def main():
    res = {"gate": {}, "tree_gates": {}, "adders": {}, "lineage": {}, "harvest": {}}
    base = {f: strip(eng("\n".join(SW["off"]) + "\n" + BODY.format(f=f))) for f in GATE}
    for sw in ("REPLICATE", "QUARANTINE", "VOTE"):
        diff = [os.path.relpath(f, WORK) for f in GATE if strip(eng("\n".join(SW[sw]) + "\n" + BODY.format(f=f))) != base[f]]
        res["gate"][sw] = {"changed": len(diff), "of": len(GATE), "datasets": diff}
        print("gate", sw, len(diff), "/", len(GATE), diff, flush=True)
    trees = os.path.join(ROOT, "studies", "trees")
    for sw in SW:
        ok = wrong = tot = 0
        for s in range(5):
            h = json.load(open(f"{trees}/hidden/gates_s{s}.json"))["hidden_outputs"]
            o = eng("\n".join(["SET TREES 1"] + SW[sw]) + f"\nINGESTFILE {trees}/obs/gates_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n")
            got = dict(facts(o, "has value"))
            for w, v in h.items():
                if v["kind"] == "rnd": continue
                tot += 1; ok += got.get(w) == v["value"]; wrong += w in got and got[w] != v["value"]
        res["tree_gates"][sw] = {"correct": ok, "wrong": wrong, "of": tot}
        ok = wrong = tot = 0
        for s in range(5):
            h = json.load(open(f"{trees}/hidden/adders_s{s}.json"))
            o = eng("\n".join(["SET TREES 1", "SET DEPTH 0"] + SW[sw]) + f"\nINGESTFILE {trees}/obs/adders_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n")
            got = dict(facts(o, "has value"))
            wires = h.get("wires") or h.get("hidden_wires") or {}
            for w, v in wires.items():
                tot += 1; ok += got.get(w) == v; wrong += w in got and got[w] != v
        res["adders"][sw] = {"correct": ok, "wrong": wrong, "of": tot}
        ok = wrong = tot = 0
        for s in range(3):
            obs, hid = lib.world("lineage", seed=s)
            o = eng("\n".join(["SET CHAIN 3"] + SW[sw]) + f"\nINGESTFILE {obs}\nRELATIONS\nINFER ALL\nCONFLICTS\nEXIT\n")
            r = lib.score(o, obs, hid); ok += r["correct"]; wrong += r["wrong"]
        res["lineage"][sw] = {"correct": ok, "wrong": wrong}
        ok = wrong = der = 0
        for s in range(3):
            lines, bad = worlds.harvest(seed=s)
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "h.txt"); open(p, "w").write("\n".join(lines) + "\n")
                o = eng("\n".join(["SET CONDITIONS 1"] + SW[sw]) + f"\nINGESTFILE {p}\nRELATIONS\nINFER ALL\nEXIT\n")
            got = facts(o, "harvests"); stated = {tuple(l.split(" harvests ")) for l in lines if " harvests " in l}
            new = got - stated; der += len(new); wrong += len(new & bad)
        res["harvest"][sw] = {"derived_new": der, "wrong_non_harvesters": wrong}
        print(sw, {k: res[k][sw] for k in ("tree_gates", "adders", "lineage", "harvest")}, flush=True)
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
