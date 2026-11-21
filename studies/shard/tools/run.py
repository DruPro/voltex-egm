"""Harness for the shard study. Generates company worlds (studies/noise/hidden/gen.py), runs one engine and the sharded
arms on the observation file only, and scores the answers against the hidden truth with studies/noise/tools/lib.py.

Usage: python3 run.py PART        PART in gate | smoke | confirm | explore
Appends one JSON line per run to ../results_PART.jsonl and skips runs already there.
"""
import hashlib, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "tools"))
import shard          # noqa: E402  (sees facts only)
import lib            # noqa: E402  (scorer; imports the generator)

BINARY = os.environ.get("VOLTEX", os.path.join(ROOT, "build", "voltex2"))
STUDY = os.path.abspath(os.path.join(HERE, ".."))
OBS, HID = os.path.join(STUDY, "obs"), os.path.join(STUDY, "hidden", "cache")
RSS_GUARD_KB = 18 * 1024 * 1024        # stop a single engine above 18 GB resident (the machine has 23 GB)

KEY = dict(boundary="key", key="is on")
COMP = dict(boundary="components", graph=("collaborates with",), attach=("works under",))
ARMS = {"S0": (KEY, False, False),  "S1": (COMP, False, False), "S2": (KEY, True, False), "S3": (COMP, True, False),
        "S4": (COMP, True, True),    "S5": (COMP, False, True),  "S6": (KEY, False, True)}   # (boundary, central, consensus)
ALL_ARMS = ["single"] + list(ARMS)
SHARDS = {2: 1, 8: 2, 16: 4, 32: 8, 64: 16}   # scale -> shards: 160 teams per shard, as in the scale study


def world(seed, scale, noise):
    tag = f"company_s{seed}_x{scale}_n{noise}"
    obs, hid = os.path.join(OBS, tag + ".txt"), os.path.join(HID, tag + ".json")
    if not (os.path.exists(obs) and os.path.exists(hid)):
        lines, h = lib.gen.company(seed=seed, scale=scale, noise=noise)
        os.makedirs(OBS, exist_ok=True); os.makedirs(HID, exist_ok=True)
        open(obs, "w").write("\n".join(lines) + "\n"); json.dump(h, open(hid, "w"))
    return obs, json.load(open(hid))


def score(answers, obs, hidden):
    text = "\n".join(f"FACT\t{f}\t{t}" for f, t in sorted(answers.items()))
    r = lib.score(text, obs, hidden)
    d = {k: r[k] for k in ("stated", "derived_new", "correct", "wrong", "precision", "recall")}
    d["answers_sha"] = hashlib.sha256("\n".join(sorted(answers)).encode()).hexdigest()[:16]
    return d


def one(seed, scale, noise, arm, n=None):
    obs, hid = world(seed, scale, noise)
    n = n or SHARDS[scale]
    base = dict(seed=seed, scale=scale, noise=noise, arm=arm)
    if arm == "single":
        lines = open(obs).read().splitlines()
        out, st = shard.run_engine(BINARY, obs, {"MAXWORDS": shard.maxwords_for(lines)}, RSS_GUARD_KB)
        if st["exit"] != 0 or st["killed"]:
            return {**base, "completed": False, **st}
        ans = {}
        for f, t in shard.facts_out(out): ans.setdefault(f, t)
        st["limit_lines"] = len(st["limit_lines"])
        return {**base, "completed": True, **st, **score(ans, obs, hid)}
    bkw, central, consensus = ARMS[arm]
    with tempfile.TemporaryDirectory(prefix="shard_") as wd:
        ans, rep = shard.shard_run(obs, wd, BINARY, n, central=central, consensus=consensus, **bkw)
        if n == 1:   # gate: with one shard and no central stage, the shard file must be the input file
            rep["shard_equals_input"] = open(os.path.join(wd, "shard00.txt")).read() == open(obs).read()
    rep.pop("engines_detail", None)
    return {**base, "n": n, "completed": rep["failed"] == 0, **rep, **score(ans, obs, hid)}


def cells(part):
    if part == "gate":
        for nz in (0.0, 0.15):
            for arm in ("single", "S0", "S1", "S5", "S6"): yield dict(seed=9, scale=2, noise=nz, arm=arm, n=1)
    if part == "smoke":
        for arm in ALL_ARMS:
            for nz in (0.0, 0.15): yield dict(seed=9, scale=8, noise=nz, arm=arm)
    if part == "confirm":
        for s in (0, 1, 2):
            for arm in ALL_ARMS: yield dict(seed=s, scale=32, noise=0.0, arm=arm)
            for arm in ALL_ARMS: yield dict(seed=s, scale=16, noise=0.15, arm=arm)
        for s in (0, 1, 2):
            for arm in ("S4", "single"): yield dict(seed=s, scale=64, noise=0.0, arm=arm)
    if part == "explore":
        for s in (0, 1, 2):
            for arm in ("single", "S4"): yield dict(seed=s, scale=32, noise=0.15, arm=arm)
            yield dict(seed=s, scale=64, noise=0.15, arm="S4")
    if part == "explore2":   # added after seeing results_explore (DEVIATIONS.md 2): is consensus needed at 122,042 + noise?
        for s in (0, 1, 2):
            for arm in ("S1", "S3", "S5"): yield dict(seed=s, scale=32, noise=0.15, arm=arm)
            for arm in ("S1", "S3"): yield dict(seed=s, scale=64, noise=0.15, arm=arm)


def main():
    part = sys.argv[1]
    out = os.path.join(STUDY, f"results_{part}.jsonl")
    done = set()
    if os.path.exists(out):
        for l in open(out):
            d = json.loads(l); done.add((d["seed"], d["scale"], d["noise"], d["arm"], d.get("n")))
    with open(out, "a") as f:
        for c in cells(part):
            n = c.get("n") or (SHARDS[c["scale"]] if c["arm"] != "single" else None)
            if (c["seed"], c["scale"], c["noise"], c["arm"], n) in done: continue
            r = one(**c)
            if c["arm"] == "single": r["n"] = None
            f.write(json.dumps(r) + "\n"); f.flush()
            print(c, {k: r.get(k) for k in ("completed", "derived_new", "wrong", "precision", "recall", "cpu",
                                            "rss_mb", "limit_lines", "unseen_lines", "shard_equals_input")}, flush=True)


if __name__ == "__main__":
    main()
