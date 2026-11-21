"""v1 (original voltex_paged.cpp, real binary) vs v2 on the same files: speed, size, memory, exactness."""
import subprocess, time, os, lzma, gzip, json, resource, shutil
V1 = "/home/claude/work/voltex"
R = {}
def v1_run(path, limit=None):
    d = "/tmp/v1run"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    lines = [l.rstrip("\n") for l in open(path)][:limit]
    cmds = "".join(f"INGEST\n{l}\n" for l in lines) + "METRICS\nSAVE\nEXIT\n"
    t = time.time(); out = subprocess.run([V1], input=cmds, capture_output=True, text=True, cwd=d).stdout; dt = time.time() - t
    roots = [l.split("Root ID: ")[1].split("\x1b")[0].strip() for l in out.replace("\x1b[1;37m", "").splitlines() if "Root ID:" in l]
    # exactness: unroll first 50 roots
    cmds2 = "LOAD\n" + "".join(f"UNROLL\n{r}\n" for r in roots[:50]) + "EXIT\n"
    o2 = subprocess.run([V1], input=cmds2, capture_output=True, text=True, cwd=d).stdout
    size = os.path.getsize(f"{d}/vault.meta") + os.path.getsize(f"{d}/vault.blob")
    return {"seconds": round(dt, 3), "store_bytes": size, "distinct_ids_for_distinct_lines": len(set(roots)), "unique_lines": len(set(lines))}
def v2_run(path):
    cmds = f"INGESTFILE {path}\nMETRICS\nSAVE /tmp/v2.vtx2\nEXIT\n"
    t = time.time(); out = subprocess.run(["./voltex2"], input=cmds, capture_output=True, text=True).stdout; dt = time.time() - t
    lines = [l.rstrip("\n") for l in open(path)]
    # exactness: unroll every record after a LOAD round-trip
    cmds2 = "LOAD /tmp/v2.vtx2\n" + "".join(f"UNROLL {i}\n" for i in range(len(set(lines)))) + "EXIT\n"
    o2 = subprocess.run(["./voltex2"], input=cmds2, capture_output=True, text=True).stdout.splitlines()[1:]
    uniq = list(dict.fromkeys(lines))
    exact = sum(a == b for a, b in zip(o2, uniq))
    m = {l.split(":")[0].strip(): l.split(":", 1)[1].strip() for l in out.splitlines() if ":" in l and not l.startswith("[")}
    return {"seconds": round(dt, 3), "save_bytes": os.path.getsize("/tmp/v2.vtx2"), "exact_after_save_load": f"{exact}/{len(uniq)}",
            "grammar": m.get("Grammar"), "rss": m.get("Process RSS"), "invariants": m.get("Invariants"),
            "ingest_line": [l for l in out.splitlines() if l.startswith("[INGEST]")][0]}
for f, v1limit in [("data/evo_1000.txt", None), ("data/license.txt", None), ("data/grammar_train.txt", None), ("data/evo_20000.txt", 20000)]:
    raw = open(f, "rb").read()
    row = {"raw_bytes": len(raw), "gzip9": len(gzip.compress(raw, 9)), "xz9": len(lzma.compress(raw, preset=9)), "v2": v2_run(f)}
    try: row["v1"] = v1_run(f, v1limit)
    except Exception as e: row["v1"] = str(e)
    R[f] = row; print(f, json.dumps(row, indent=1))
json.dump(R, open("results_bench.json", "w"), indent=1)
