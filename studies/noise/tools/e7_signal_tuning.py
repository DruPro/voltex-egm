"""E7 (EXPLORATORY, designed after seeing E6): signal-focused self-tuning on fresh seeds 3-5. Conditions: default,
self-tuning as registered (focus=all), signal-focused self-tuning, oracle. Writes results_tuning_signal.json."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e6_tuning as E6
import lib
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_tuning_signal.json")


def main():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for world in E6.WORLDS:
        for seed in (3, 4, 5):
            key = f"{world}/{seed}"
            if key in res: continue
            obs, hid, rels, truth, stated, missing, ext_pairs, _ = E6.split(world, seed)
            t0 = time.time(); a = E6.T.tune(obs, seed=0, binary=lib.VOLTEX); t1 = time.time()
            s = E6.T.tune(obs, seed=0, binary=lib.VOLTEX, focus="signal"); t2 = time.time()
            all_pairs = {(r, x) for r, x, _ in truth} - ext_pairs
            o = E6.T.tune(obs, labels=[f"{x} {r} {b}" for r, x, b in missing if (r, x) not in ext_pairs], label_pairs=all_pairs, binary=lib.VOLTEX)
            row = {"world": world, "seed": seed, "self_settings": a.settings, "signal_settings": s.settings, "oracle_settings": o.settings,
                   "seconds": {"self": round(t1 - t0, 1), "signal": round(t2 - t1, 1)}}
            for cond, st in (("default", {}), ("self", a.settings), ("signal", s.settings), ("oracle", o.settings)):
                row[cond] = E6.test_score(obs, st, rels, stated, missing, ext_pairs, truth)
            res[key] = row; json.dump(res, open(OUT, "w"), indent=1)
            print(key, {c: round(row[c]["f05"], 4) for c in ("default", "self", "signal", "oracle")}, "self", a.settings, "signal", s.settings, "oracle", o.settings, flush=True)


if __name__ == "__main__":
    main()
