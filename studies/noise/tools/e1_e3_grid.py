"""E1-E3 (accumulation, REPLICATE, QUARANTINE) and the hidden coverage sweep. Writes results_grid.jsonl, one line per run.
Usage: python3 e1_e3_grid.py [part]   part in company|hidden|coverage|gates (default all)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

CONF = {"base": {}, "R": {"REPLICATE": 1}, "Q": {"QUARANTINE": 1}, "RQ": {"REPLICATE": 1, "QUARANTINE": 1},
        "T": {"TREES": 1}, "TR": {"TREES": 1, "REPLICATE": 1}, "TQ": {"TREES": 1, "QUARANTINE": 1},
        "TRQ": {"TREES": 1, "REPLICATE": 1, "QUARANTINE": 1}}
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def cells(part):
    if part in ("all", "company"):
        for sc in (0.5, 1.0, 2.0, 4.0):
            for nz in (0.0, 0.15, 0.30):
                for s in (0, 1, 2):
                    yield "company", dict(seed=s, scale=sc, noise=nz, reports=1), list(CONF)
    if part in ("all", "hidden"):
        for sc in (1, 2, 4):
            for nz in (0.03, 0.15, 0.30):
                for s in (0, 1, 2):
                    yield "hidden", dict(seed=s, scale=sc, coverage=0.5, noise=nz, reports=1), list(CONF)
    if part in ("all", "coverage"):
        for cv in (0.3, 0.5, 0.7, 0.9):
            for s in (0, 1, 2):
                yield "hidden", dict(seed=s, scale=1, coverage=cv, noise=0.15, reports=1), ["base", "R", "Q", "RQ"]
    if part in ("all", "gates"):
        for pk in (100, 200, 400, 800):
            for nz in (0.0, 0.05, 0.15):
                for s in (0, 1, 2):
                    yield "gates", dict(seed=s, per_kind=pk, noise=nz), ["T", "TR", "TQ", "TRQ"]


def main():
    part = sys.argv[1] if len(sys.argv) > 1 else "all"
    OUT = os.path.join(OUT_DIR, f"results_grid_{part}.jsonl")
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT): d = json.loads(l); done.add((d["world"], json.dumps(d["params"], sort_keys=True), d["config"]))
    with open(OUT, "a") as f:
        for w, kw, confs in cells(part):
            obs, hid = lib.world(w, **kw)
            for c in confs:
                key = (w, json.dumps(kw, sort_keys=True), c)
                if key in done: continue
                st = lib.settings_lines(CONF[c]); t = time.time()
                out = lib.run(obs, st)
                r = lib.score(out, obs, hid, with_causes=True, settings=st)
                r.update(world=w, params=kw, config=c, seconds=round(time.time() - t, 2))
                f.write(json.dumps(r) + "\n"); f.flush()
                print(w, kw, c, r["derived_new"], r["wrong"], round(r["precision"], 4), round(r["recall"], 4), r["seconds"], flush=True)


if __name__ == "__main__":
    main()
