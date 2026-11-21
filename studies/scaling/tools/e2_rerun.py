"""E2 rerun (DEVIATIONS.md 2): save raw outputs of frozen and variant, compare after dropping only the variant's
[SET] CLUSTERSTREAM echo. Appends to ../results_e2.jsonl."""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit, compare
OUT = os.path.join(audit.STUDY, "logs", "e2"); os.makedirs(OUT, exist_ok=True)
with open(os.path.join(audit.STUDY, "results_e2.jsonl"), "a") as f:
    for name, kw in compare.CELLS:
        p, tag = audit.world(name, **kw)
        lines = open(p).read().splitlines()
        st = {"PROFILE": 1, "MAXWORDS": audit.shard.maxwords_for(lines)}
        if name == "gates": st["TREES"] = 1
        outs = {}
        for eng, binary, extra in (("frozen", compare.FROZEN, {}), ("stream", compare.LAB, {"CLUSTERSTREAM": 1})):
            out, _ = audit.shard.run_engine(binary, p, {**extra, **st})
            open(os.path.join(OUT, f"{tag}.{eng}.out"), "w").write(out)
            c = compare.clean(out)
            if eng == "stream": c = "\n".join(l for l in c.splitlines() if not l.startswith("[SET] CLUSTERSTREAM = "))
            outs[eng] = c
        a, b = outs["frozen"].splitlines(), outs["stream"].splitlines()
        diff = [x for x in zip(a, b) if x[0] != x[1]][:5]
        r = {"tag": tag, "identical": outs["frozen"] == outs["stream"], "lines_frozen": len(a), "lines_stream": len(b),
             "sha": hashlib.sha256(outs["frozen"].encode()).hexdigest()[:16], "first_diffs": diff}
        f.write(json.dumps(r) + "\n"); f.flush(); print(tag, r["identical"], len(a), len(b), diff[:2], flush=True)
