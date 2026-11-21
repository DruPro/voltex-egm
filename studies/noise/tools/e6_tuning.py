"""E6 tuning: default vs self-tuned vs external-label-tuned vs oracle-tuned, plus transfer. Writes results_tuning.json.
Self-tuning runs in a separate Python process that is given only the observation file; an audit hook records every
file it opens (H6f)."""
import json, os, random, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
import importlib  # noqa: E402
T = importlib.import_module("egm.tune")  # the module (egm.tune the attribute is the function)

WORLDS = {"company15": ("company", dict(scale=1.0, noise=0.15, reports=1)),
          "company30": ("company", dict(scale=1.0, noise=0.30, reports=1)),
          "hidden_c50": ("hidden", dict(scale=1, coverage=0.5, noise=0.03, reports=1)),
          "hidden_c30": ("hidden", dict(scale=1, coverage=0.3, noise=0.15, reports=1)),
          "gates": ("gates", dict(per_kind=200, noise=0.05)),
          "lineage": ("lineage", {})}
SEEDS = (0, 1, 2)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_tuning.json")
SELF = r"""
import json, sys
opened = []
def hook(ev, args):
    if ev == "open" and args and isinstance(args[0], (str, bytes)): opened.append(args[0] if isinstance(args[0], str) else args[0].decode())
sys.addaudithook(hook)
sys.path.insert(0, sys.argv[2])
import egm
r = egm.tune(sys.argv[1], seed=0)
print(json.dumps({"settings": r.settings, "baseline": r.baseline, "tuned": r.tuned, "evaluations": r.evaluations,
                  "history": r.history, "opened": sorted(set(opened))}))
"""


def split(world, seed):
    name, kw = WORLDS[world]
    obs, hid = lib.world(name, seed=seed, **kw)
    rels = sorted(hid["relations"], key=len, reverse=True)
    truth = {tuple(x) for x in hid["truth"]}
    stated = lib.facts_of(open(obs).read().splitlines(), rels)
    unseen = set(hid.get("unseen", []))
    missing = {f for f in truth - stated if f[1] not in unseen and f[2] not in unseen}
    pairs = sorted({(r, a) for r, a, _ in missing})
    ext_pairs = set(random.Random(7000 + seed).sample(pairs, max(1, len(pairs) // 10)))
    ext_labels = sorted(f for f in missing if (f[0], f[1]) in ext_pairs)
    return obs, hid, rels, truth, stated, missing, ext_pairs, ext_labels


def test_score(obs, settings, rels, stated, missing, ext_pairs, truth):
    out = lib.run(obs, lib.settings_lines(settings))
    derived = set()
    for l in out.splitlines():
        if l.startswith("FACT\t"):
            f = lib.parse_fact(l.split("\t")[1], rels)
            if f: derived.add(f)
    new = {f for f in derived - stated if (f[0], f[1]) not in ext_pairs}
    miss = {f for f in missing if (f[0], f[1]) not in ext_pairs}
    ok = len(new & truth); p = ok / len(new) if new else 1.0; r = len(new & miss) / len(miss) if miss else 0.0
    return {"f05": T._f(p, r), "precision": p, "recall": r, "derived_new": len(new), "wrong": len(new - truth)}


def main():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {"runs": {}, "transfer_within": [], "transfer_cross": []}
    for world in WORLDS:
        for seed in SEEDS:
            key = f"{world}/{seed}"
            if key in res["runs"]: continue
            obs, hid, rels, truth, stated, missing, ext_pairs, ext_labels = split(world, seed)
            t0 = time.time()
            p = subprocess.run([sys.executable, "-c", SELF, obs, ROOT], capture_output=True, text=True, env={**os.environ, "EGM_VOLTEX": lib.VOLTEX})
            if p.returncode != 0: raise SystemExit(p.stderr)
            self_r = json.loads(p.stdout.strip().splitlines()[-1]); t1 = time.time()
            hidden_dir = os.path.abspath(os.path.join(os.path.dirname(lib.__file__), "..", "hidden"))
            leaks = [o for o in self_r["opened"] if os.path.abspath(o).startswith(hidden_dir)]
            ext = T.tune(obs, labels=[f"{a} {r} {b}" for r, a, b in ext_labels], label_pairs=ext_pairs, binary=lib.VOLTEX); t2 = time.time()
            all_pairs = {(r, a) for r, a, _ in truth} - ext_pairs
            orc = T.tune(obs, labels=[f"{a} {r} {b}" for r, a, b in missing if (r, a) not in ext_pairs], label_pairs=all_pairs, binary=lib.VOLTEX); t3 = time.time()
            row = {"world": world, "seed": seed, "self_settings": self_r["settings"], "ext_settings": ext.settings, "oracle_settings": orc.settings,
                   "self_objective": [self_r["baseline"], self_r["tuned"]], "ext_objective": [ext.baseline, ext.tuned], "oracle_objective": [orc.baseline, orc.tuned],
                   "self_evaluations": self_r["evaluations"], "hidden_files_opened_by_self_tuner": leaks, "files_opened_by_self_tuner": self_r["opened"],
                   "seconds": {"self": round(t1 - t0, 1), "ext": round(t2 - t1, 1), "oracle": round(t3 - t2, 1)}, "self_history": self_r["history"],
                   "n_ext_labels": len(ext_labels), "n_ext_pairs": len(ext_pairs)}
            for cond, st in (("default", {}), ("self", self_r["settings"]), ("ext", ext.settings), ("oracle", orc.settings)):
                row[cond] = test_score(obs, st, rels, stated, missing, ext_pairs, truth)
            res["runs"][key] = row
            json.dump(res, open(OUT, "w"), indent=1)
            print(key, {c: round(row[c]["f05"], 4) for c in ("default", "self", "ext", "oracle")}, "self:", row["self_settings"], "ext:", ext.settings,
                  "oracle:", orc.settings, row["seconds"], "leaks", leaks, flush=True)
    # transfer: within world (seed s settings on the other seeds), across worlds (seed-0 settings of A on B, seed 1)
    if not res["transfer_within"]:
        for world in WORLDS:
            for s in SEEDS:
                st = res["runs"][f"{world}/{s}"]["self_settings"]
                for o in SEEDS:
                    if o == s: continue
                    obs, hid, rels, truth, stated, missing, ext_pairs, _ = split(world, o)
                    sc = test_score(obs, st, rels, stated, missing, ext_pairs, truth)
                    res["transfer_within"].append({"world": world, "tuned_on": s, "applied_to": o, "settings": st, **sc,
                                                   "default_f05": res["runs"][f"{world}/{o}"]["default"]["f05"],
                                                   "own_self_f05": res["runs"][f"{world}/{o}"]["self"]["f05"]})
        json.dump(res, open(OUT, "w"), indent=1)
    if not res["transfer_cross"]:
        for a in WORLDS:
            st = res["runs"][f"{a}/0"]["self_settings"]
            for b in WORLDS:
                if a == b: continue
                obs, hid, rels, truth, stated, missing, ext_pairs, _ = split(b, 1)
                sc = test_score(obs, st, rels, stated, missing, ext_pairs, truth)
                res["transfer_cross"].append({"from": a, "to": b, "settings": st, **sc, "default_f05": res["runs"][f"{b}/1"]["default"]["f05"],
                                              "own_self_f05": res["runs"][f"{b}/1"]["self"]["f05"]})
        json.dump(res, open(OUT, "w"), indent=1)
    print("done")


if __name__ == "__main__":
    main()
