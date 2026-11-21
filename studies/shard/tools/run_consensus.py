"""Pre-registered consensus test (PREREGISTRATION_CONSENSUS.md). Uses run.one() unchanged. Appends to
../results_consensus.jsonl. Usage: python3 run_consensus.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run   # noqa: E402

SEEDS = (3, 4, 5)
CELLS = []
for s in SEEDS:
    CELLS += [dict(seed=s, scale=32, noise=0.15, n=8), dict(seed=s, scale=64, noise=0.15, n=16),
              dict(seed=s, scale=16, noise=0.15, n=8), dict(seed=s, scale=32, noise=0.0, n=8)]


def main():
    out = os.path.join(run.STUDY, "results_consensus.jsonl")
    done = set()
    if os.path.exists(out):
        for l in open(out): d = json.loads(l); done.add((d["seed"], d["scale"], d["noise"], d["arm"], d.get("n")))
    with open(out, "a") as f:
        for c in CELLS:
            for arm in ("single", "S1", "S5"):
                n = None if arm == "single" else c["n"]
                if (c["seed"], c["scale"], c["noise"], arm, n) in done: continue
                r = run.one(c["seed"], c["scale"], c["noise"], arm, n=n)
                if arm == "single": r["n"] = None
                f.write(json.dumps(r) + "\n"); f.flush()
                print(c, arm, {k: r.get(k) for k in ("completed", "wrong", "precision", "recall", "cpu", "rss_mb", "dropped")}, flush=True)


if __name__ == "__main__":
    main()
