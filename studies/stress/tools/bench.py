"""Stress bench (studies/stress): many varied datasets x settings x scripts, so an engine change is judged on more than
one use case. Temporary layers in ../layers turn real code, real tables and synthetic shapes into facts.

  python3 bench.py catalog                  build every dataset into ../obs (git-ignored), keys into ../obs/keys,
                                            write ../manifest.json (sizes, sha256, source line counts)
  python3 bench.py run BIN OUT [opts]       run every cell with binary BIN, append JSON lines to OUT
       --only SUBSTR   cells whose id contains SUBSTR      --set K=V   extra setting for this binary only
       --env K=V       environment for the binary          --tier T    light | full (default full)
  python3 bench.py compare A.jsonl B.jsonl  equivalence (output hash per cell) and cost ratios

Each cell runs in a fresh process with /usr/bin/time (peak RSS of the engine alone), a memory cap (ulimit -v) and a
timeout. Output is compared after dropping lines that legitimately vary (throughput, [PROFILE], [LAB], RSS, [SET] echo
and k=v tokens inside [CONFIG], as studies/scaling/tools/gate.py does).
"""
import glob, hashlib, json, os, random, re, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", ".."))
OBS = os.path.join(STUDY, "obs"); KEYS = os.path.join(OBS, "keys")
sys.path.insert(0, os.path.join(STUDY, "layers")); sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "hidden"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
MEM_CAP_KB = 12 * 1024 * 1024
TIMEOUT = 900
HIDE = 0.2


def held_out(facts, seed):
    """Seeded split of real facts: 80% stated, 20% the hidden key."""
    r = random.Random(seed); s, k = [], []
    for f in facts: (k if r.random() < HIDE else s).append(f)
    return s, k


def sources():
    """name -> callable returning (lines, key, meta). Real sources hold out 20%; generators define their own key."""
    import codebase, world, synth, gen, worlds as tw
    home = os.path.expanduser("~")
    js_roots = sorted(glob.glob(os.path.join(home, ".vscode", "extensions", "*", "node_modules")))

    def real(fn, seed=11):
        def f():
            facts, meta = fn(); s, k = held_out(facts, seed); return s, k, meta
        return f

    def synthetic(fn, **kw):
        def f():
            lines, key = fn(**kw); return lines, key, {}
        return f

    def g(fn, **kw):
        def f():
            out = fn(**kw); lines, hid = out[0], out[1]
            key = []
            if isinstance(hid, dict) and "truth" in hid:
                st = set(lines); key = [" ".join([t[1], t[0], t[2]]) for t in hid["truth"]]
                key = [k for k in key if k not in st]
            return lines, key, {}
        return f

    S = {
        # code layer: four languages / corpora, each over 100k source lines, plus all of them in one engine
        "code_py_stdlib": real(lambda: codebase.python([("/usr/lib/python3.13", "py")])),
        "code_py_dist": real(lambda: codebase.python([("/usr/lib/python3/dist-packages", "dp")], max_lines=400000)),
        "code_c_headers": real(lambda: codebase.c_headers("/usr/include", max_lines=400000)),
        "code_js": real(lambda: codebase.js(js_roots)),
        "code_mixed": real(lambda: _concat(codebase.python([("/usr/lib/python3.13", "py")]),
                                           codebase.c_headers("/usr/include", max_lines=400000), codebase.js(js_roots))),
        # world-data layer: real tables of different shapes, and all of them in one engine
        "world_packages": real(world.packages),
        "world_unicode": real(world.unicode),
        "world_timezones": real(world.timezones),
        "world_services": real(world.services),
        "world_mixed": real(lambda: _concat(world.packages(), world.unicode(), world.timezones(), world.services())),
    }
    for name, fn in synth.SHAPES.items():
        S["synth_" + name] = synthetic(fn)
    S["synth_zipf_big"] = synthetic(synth.zipf, n=30000)
    S["synth_clusters_big"] = synthetic(synth.clusters, n=40000, c=400)
    S.update({
        "gen_company1": g(gen.company, seed=0, scale=1), "gen_company8": g(gen.company, seed=0, scale=8),
        "gen_company32": g(gen.company, seed=0, scale=32), "gen_company4_n15": g(gen.company, seed=0, scale=4, noise=0.15),
        "gen_hidden1": g(gen.hidden, seed=0, scale=1), "gen_hidden8": g(gen.hidden, seed=0, scale=8),
        "gen_gates200": g(gen.gates, seed=0, per_kind=200), "gen_gates2400": g(gen.gates, seed=0, per_kind=2400),
        "gen_lineage": g(gen.lineage, seed=0),
        "t_remainders": synthetic(lambda: (tw.remainders()[0], [])), "t_harvest": synthetic(lambda: (tw.harvest()[0], [])),
        "t_staff_noisy": synthetic(lambda: (tw.staff(noise=0.15, reports=3)[0], [])),
    })
    return S


def _concat(*parts):
    facts, meta = [], {}
    for i, (f, m) in enumerate(parts): facts += f; meta[f"part{i}"] = m
    return sorted(set(facts)), meta


VARIETY = {"trees": {"TREES": 1}, "chain3": {"CHAIN": 3}, "class03": {"CLASS": 0.3}, "class07": {"CLASS": 0.7},
           "depth0": {"DEPTH": 0}, "cov0": {"COVERAGE": 0}, "tsteps0": {"TENDENCYSTEPS": 0}, "conditions": {"CONDITIONS": 1},
           "maxwords300": {"MAXWORDS": 300}}


def cells(manifest, tier="full"):
    """Every dataset: default settings and, when its vocabulary passes the default cap, MAXWORDS sized to it.
    Datasets under 40,000 facts also get every VARIETY setting. Every dataset also gets the update script."""
    for name, m in sorted(manifest.items()):
        yield f"{name}|default|full", name, {}, "full"
        if m["words"] > 11000: yield f"{name}|sized|full", name, {"MAXWORDS": m["words"] + 1000}, "full"
        sized = {"MAXWORDS": m["words"] + 1000} if m["words"] > 11000 else {}
        yield f"{name}|{'sized' if sized else 'default'}|update", name, sized, "update"
        if tier == "full" and m["facts"] < 40000:
            for vn, st in VARIETY.items():
                yield f"{name}|{vn}|full", name, {**sized, **st} if vn != "maxwords300" else st, "full"


def script(name, st, kind, kb):
    p = os.path.join(OBS, name + ".txt")
    head = [f"SET {k} {v}" for k, v in st.items()]
    if kind == "full":
        body = [f"INGESTFILE {p}", "RELATIONS", "INFER ALL", "CONFLICTS", "CLASSES", "CHAINS", "METRICS",
                f"SAVE {kb}", f"LOAD {kb}", "INFER ALL"]
    else:   # update: 90% first, query, then the last 10% in two steps with a query after each
        body = [f"INGESTFILE {os.path.join(OBS, name + '.a.txt')}", "INFER ALL",
                f"INGESTFILE {os.path.join(OBS, name + '.b.txt')}", "INFER ALL",
                f"INGESTFILE {os.path.join(OBS, name + '.c.txt')}", "INFER ALL", "CONFLICTS"]
    return "\n".join(head + body + ["EXIT"]) + "\n"


VARY = re.compile(r"MB/s|Process RSS|^\[PROFILE\]|^\[LAB\]|^\[SET\]")


def clean(out):
    keep = []
    for l in out.splitlines():
        if VARY.search(l): continue
        if l.startswith("[CONFIG]"): l = re.sub(r" \w+=\S+", "", l)
        l = re.sub(r"(restored from |saved to )\S+", r"\1KB", l)   # the knowledge base's temp path differs per run (DEVIATIONS 1)
        keep.append(l)
    return "\n".join(keep)


def catalog():
    os.makedirs(KEYS, exist_ok=True); man = {}
    for name, fn in sources().items():
        t = time.time(); lines, key, meta = fn()
        lines = [l for l in lines]
        p = os.path.join(OBS, name + ".txt"); open(p, "w").write("\n".join(lines) + "\n")
        n = len(lines); a, b = int(n * 0.9), int(n * 0.95)
        open(os.path.join(OBS, name + ".a.txt"), "w").write("\n".join(lines[:a]) + "\n")
        open(os.path.join(OBS, name + ".b.txt"), "w").write("\n".join(lines[a:b]) + "\n")
        open(os.path.join(OBS, name + ".c.txt"), "w").write("\n".join(lines[b:]) + "\n")
        open(os.path.join(KEYS, name + ".key"), "w").write("\n".join(key) + "\n")
        words = len({w for l in lines for w in l.split()})
        man[name] = {"facts": n, "key": len(key), "words": words, "meta": meta,
                     "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "gen_s": round(time.time() - t, 1)}
        print(name, man[name], flush=True)
    json.dump(man, open(os.path.join(STUDY, "manifest.json"), "w"), indent=1, sort_keys=True)


def quality(out, name):
    stated = {" ".join(l.split()) for l in open(os.path.join(OBS, name + ".txt"))}
    key = {" ".join(l.split()) for l in open(os.path.join(KEYS, name + ".key")) if l.strip()}
    derived = set()
    for l in out.split("\n"):
        if l.startswith("FACT\t"): derived.add(" ".join(l.split("\t")[1].split()))
    new = derived - stated; hit = new & key
    q = {"derived_new": len(new), "key_hit": len(hit)}
    if key: q.update(precision=round(len(hit) / len(new), 4) if new else None, recall=round(len(hit) / len(key), 4))
    return q


def run_cell(binary, cid, name, st, kind, env):
    with tempfile.TemporaryDirectory() as td:
        kb = os.path.join(td, "kb.vtx"); tf = os.path.join(td, "time.txt")
        cmd = ["bash", "-c", f'ulimit -v {MEM_CAP_KB}; exec /usr/bin/time -f "%e %M" -o {tf} timeout {TIMEOUT} {binary}']
        t = time.time()
        p = subprocess.run(cmd, input=script(name, st, kind, kb), capture_output=True, text=True, env={**os.environ, **env})
        wall = time.time() - t
        out = p.stdout + p.stderr
        tl = open(tf).read().split() if os.path.exists(tf) else []
        try: el, rss = float(tl[-2]), int(tl[-1]) / 1024
        except (IndexError, ValueError): el, rss = wall, None
        c = clean(out)
        r = {"cell": cid, "dataset": name, "settings": st, "script": kind, "status": p.returncode, "s": el,
             "peak_mb": round(rss, 1) if rss else None, "hash": hashlib.sha256(c.encode()).hexdigest()[:16],
             "lines": c.count("\n"), "limit": sum(1 for l in out.splitlines() if l.startswith("[LIMIT]"))}
        if p.returncode == 0: r.update(quality(out, name))
        else: r["tail"] = out[-300:]
        return r


def run(binary, out_path, only=None, extra=None, env=None, tier="full"):
    man = json.load(open(os.path.join(STUDY, "manifest.json")))
    done = set()
    if os.path.exists(out_path): done = {json.loads(l)["cell"] for l in open(out_path)}
    for cid, name, st, kind in cells(man, tier):
        if only and not any(o in cid for o in only.split(",")): continue
        if os.environ.get("BENCH_SETTINGS_ONLY") and not st: continue   # DEVIATIONS 1: rerun only cells with settings
        if cid in done: continue
        r = run_cell(binary, cid, name, {**st, **(extra or {})}, kind, env or {})
        with open(out_path, "a") as fh: fh.write(json.dumps(r) + "\n")
        print(f"{cid:44s} st={r['status']} {r['s']:7.2f}s {r['peak_mb']}MB {r['hash']} "
              f"P={r.get('precision')} R={r.get('recall')} new={r.get('derived_new')}", flush=True)


def compare(a, b):
    A = {json.loads(l)["cell"]: json.loads(l) for l in open(a)}; B = {json.loads(l)["cell"]: json.loads(l) for l in open(b)}
    same = diff = capped = 0; ts = []
    for c in sorted(set(A) & set(B)):
        x, y = A[c], B[c]
        if x["status"] != 0 or y["status"] != 0:
            capped += 1; print("NOT COMPARABLE", c, x["status"], y["status"]); continue
        if x["hash"] == y["hash"]: same += 1
        else: diff += 1; print("DIFFERENT", c)
        ts.append((c, x["s"], y["s"], x["peak_mb"], y["peak_mb"]))
    print(f"identical {same}, different {diff}, not comparable {capped}, missing {len(set(A) ^ set(B))}")
    return same, diff, capped


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "catalog": catalog()
    elif a[0] == "run":
        opt = {"only": None, "extra": {}, "env": {}, "tier": "full"}
        i = 3
        while i < len(a):
            if a[i] == "--only": opt["only"] = a[i + 1]
            elif a[i] == "--set": k, v = a[i + 1].split("="); opt["extra"][k] = v
            elif a[i] == "--env": k, v = a[i + 1].split("="); opt["env"][k] = v
            elif a[i] == "--tier": opt["tier"] = a[i + 1]
            i += 2
        run(a[1], a[2], **opt)
    elif a[0] == "compare": sys.exit(1 if compare(a[1], a[2])[1] else 0)
