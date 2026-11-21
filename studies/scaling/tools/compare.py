"""E2, M1-M3: frozen engine vs lab copy with CLUSTERSTREAM 1 on large worlds. Appends to ../results_compare.jsonl.
Usage: python3 compare.py"""
import hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit   # world(), shard.run_engine
STUDY = audit.STUDY
FROZEN = os.path.join(STUDY, "lab", "frozen_voltex2"); LAB = os.path.join(STUDY, "lab", "voltex2_lab")
CELLS = ([("company", dict(seed=s, scale=32, noise=0.0)) for s in (0, 1, 2)] +
         [("gates", dict(seed=s, per_kind=1600, noise=0.0)) for s in (0, 1, 2)] +
         [("company", dict(seed=s, scale=64, noise=0.0)) for s in (0, 1)] +
         [("hidden", dict(seed=s, scale=8, coverage=0.5, noise=0.03)) for s in (0, 1)])


def clean(out):
    return "\n".join(l for l in out.splitlines() if "MB/s" not in l and not l.startswith("[PROFILE]") and not l.startswith("[LAB]"))


def main():
    path = os.path.join(STUDY, "results_compare.jsonl")
    done = {(json.loads(l)["tag"], json.loads(l)["engine"]) for l in open(path)} if os.path.exists(path) else set()
    with open(path, "a") as f:
        for name, kw in CELLS:
            p, tag = audit.world(name, **kw)
            lines = open(p).read().splitlines()
            st = {"PROFILE": 1, "MAXWORDS": audit.shard.maxwords_for(lines)}
            if name == "gates": st["TREES"] = 1
            for eng, binary, extra in (("frozen", FROZEN, {}), ("stream", LAB, {"CLUSTERSTREAM": 1})):
                if (tag, eng) in done: continue
                out, r = audit.shard.run_engine(binary, p, {**extra, **st}, rss_limit_kb=20 * 1024 * 1024)
                m = re.search(r"\[PROFILE\] classes ([\d.]+) ms \| relations ([\d.]+) ms \| rule mining ([\d.]+) ms", out)
                mi = re.search(r"\[PROFILE\] infer ([\d.]+) ms", out)
                r.update(tag=tag, world=name, params=kw, facts=len(lines), engine=eng, limit_lines=len(r["limit_lines"]),
                         classes_ms=float(m.group(1)) if m else None, relations_ms=float(m.group(2)) if m else None,
                         mining_ms=float(m.group(3)) if m else None, infer_ms=float(mi.group(1)) if mi else None,
                         out_sha=hashlib.sha256(clean(out).encode()).hexdigest(), out_lines=out.count("\n"))
                f.write(json.dumps(r) + "\n"); f.flush()
                print(tag, eng, r["cpu"], r["rss_mb"], r["classes_ms"], r["out_sha"][:12], r["exit"], flush=True)


if __name__ == "__main__":
    main()
