"""Gate for the SDK helper egm.shard: it must reproduce the answer sets the study harness recorded (answers_sha in the
results files) for every arm, shard count and noise level below. Usage: python3 gate_sdk.py   Writes ../results_gate_sdk.json"""
import hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
import egm   # noqa: E402
STUDY = os.path.abspath(os.path.join(HERE, ".."))
ARMS = {"S0": dict(key="is on"), "S1": dict(graph=["collaborates with"], attach=["works under"]),
        "S2": dict(key="is on", central=True), "S3": dict(graph=["collaborates with"], attach=["works under"], central=True),
        "S4": dict(graph=["collaborates with"], attach=["works under"], central=True, consensus=True),
        "S5": dict(graph=["collaborates with"], attach=["works under"], consensus=True), "S6": dict(key="is on", consensus=True)}
CELLS = [("results_smoke.jsonl", 9, 8, 0.0, list(ARMS)), ("results_smoke.jsonl", 9, 8, 0.15, list(ARMS)),
         ("results_confirm.jsonl", 0, 16, 0.15, list(ARMS)), ("results_explore2.jsonl", 0, 32, 0.15, ["S1", "S5"]),
         ("results_consensus.jsonl", 4, 64, 0.15, ["S1", "S5"])]


def recorded(fname, seed, scale, noise, arm):
    for l in open(os.path.join(STUDY, fname)):
        d = json.loads(l)
        if (d["seed"], d["scale"], d["noise"], d["arm"]) == (seed, scale, noise, arm): return d
    raise KeyError((fname, seed, scale, noise, arm))


rows, ok = [], 0
for fname, seed, scale, noise, arms in CELLS:
    obs = os.path.join(STUDY, "obs", f"company_s{seed}_x{scale}_n{noise}.txt")
    for arm in arms:
        d = recorded(fname, seed, scale, noise, arm)
        kw = {"consensus": False, **ARMS[arm]}
        for jobs in ((1, 8) if scale == 64 else (1,)):
            t = time.time(); r = egm.shard(obs, d["n"], jobs=jobs, **kw); sec = round(time.time() - t, 2)
            sha = hashlib.sha256("\n".join(sorted(f.fact for f in r.facts)).encode()).hexdigest()[:16]
            rows.append(dict(cell=f"{fname}:{seed}:{scale}:{noise}", arm=arm, n=d["n"], jobs=jobs, identical=sha == d["answers_sha"],
                             facts=len(r.facts), wall_s=sec, warnings=r.warnings))
            ok += sha == d["answers_sha"]
            print(rows[-1]["cell"], arm, "n", d["n"], "jobs", jobs, "identical" if sha == d["answers_sha"] else "DIFFERS", len(r.facts), sec, r.warnings, flush=True)
json.dump({"identical": ok, "runs": len(rows), "rows": rows}, open(os.path.join(STUDY, "results_gate_sdk.json"), "w"), indent=1)
print(f"egm.shard gate: {ok}/{len(rows)} identical to the study harness")
