"""Tendency study T1-T7. Uses the noise study's generator and scorer (studies/noise). Writes results_*.json here.
Usage: python3 run_all.py [t1t3|t2|t5|t6|t7|all]"""
import collections, json, os, statistics, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, "..")
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "tools")); sys.path.insert(0, os.path.join(ROOT, "tests"))
import lib, worlds  # noqa: E402
TS = {"off": [], "ts1": ["SET TENDENCYSTEPS 1"], "ts0": ["SET TENDENCYSTEPS 0"]}


def eng(cmds):
    return subprocess.run([lib.VOLTEX], input=cmds, capture_output=True, text=True).stdout


def dump(name, obj):
    json.dump(obj, open(os.path.join(D, name), "w"), indent=1)


def t1t3():
    rows = []
    cells = [("hidden", dict(scale=1, coverage=cv, noise=nz, reports=1, **({"contradict": 0.0} if nz == 0 else {})))
             for cv in (0.3, 0.5, 0.7, 0.9) for nz in (0.0, 0.03)] + [("company", dict(scale=1.0, noise=nz, reports=1)) for nz in (0.0, 0.15)]
    for w, kw in cells:
        for s in (0, 1, 2):
            obs, hid = lib.world(w, seed=s, **kw)
            for c, st in TS.items():
                t = time.time(); out = lib.run(obs, st, "CHAINS"); r = lib.score(out, obs, hid)
                r.update(world=w, params={**kw, "seed": s}, config=c, seconds=round(time.time() - t, 2),
                         chains=[l.strip() for l in out.splitlines() if l.startswith("  round ")])
                rows.append(r); print(w, kw, s, c, r["derived_new"], r["correct"], round(r["precision"], 4), round(r["recall"], 3), flush=True)
    dump("results_t1_t3.json", rows)


def t2():
    trees = os.path.join(ROOT, "studies", "trees"); res = {}
    for c, st in TS.items():
        ok = wrong = 0
        for s in range(5):
            h = json.load(open(f"{trees}/hidden/gates_s{s}.json"))["hidden_outputs"]
            o = eng("\n".join(["SET TREES 1"] + st) + f"\nINGESTFILE {trees}/obs/gates_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n")
            got = {l.split("\t")[1].split(" has value ")[0]: l.split("\t")[1].split(" has value ")[1] for l in o.splitlines() if l.startswith("FACT\t") and " has value " in l}
            for wv, v in h.items():
                if v["kind"] != "rnd": ok += got.get(wv) == v["value"]; wrong += wv in got and got[wv] != v["value"]
        res.setdefault("tree_gates", {})[c] = {"correct": ok, "wrong": wrong}
        ok = wrong = 0
        for s in range(5):
            h = json.load(open(f"{trees}/hidden/adders_s{s}.json"))["hidden_wires"]
            o = eng("\n".join(["SET TREES 1", "SET DEPTH 0"] + st) + f"\nINGESTFILE {trees}/obs/adders_s{s}.txt\nRELATIONS\nINFER ALL\nEXIT\n")
            got = {l.split("\t")[1].split(" has value ")[0]: l.split("\t")[1].split(" has value ")[1] for l in o.splitlines() if l.startswith("FACT\t") and " has value " in l}
            for wv, v in h.items(): ok += got.get(wv) == v; wrong += wv in got and got[wv] != v
        res.setdefault("adders", {})[c] = {"correct": ok, "wrong": wrong}
        ok = wrong = 0
        for s in range(3):
            obs, hid = lib.world("lineage", seed=s); r = lib.score(eng("\n".join(["SET CHAIN 3"] + st) + f"\nINGESTFILE {obs}\nRELATIONS\nINFER ALL\nEXIT\n"), obs, hid)
            ok += r["correct"]; wrong += r["wrong"]
        res.setdefault("lineage", {})[c] = {"correct": ok, "wrong": wrong}
        ok = wrong = 0
        for s in range(3):
            lines, key = worlds.remainders(seed=s)
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "r.txt"); open(p, "w").write("\n".join(lines) + "\n")
                o = eng("\n".join(["SET DEPTH 0"] + st) + f"\nINGESTFILE {p}\nRELATIONS\nINFER ALL\nEXIT\n")
            got = {l.split("\t")[1].split(" has remainder ")[0]: l.split("\t")[1].split(" has remainder ")[1] for l in o.splitlines() if l.startswith("FACT\t") and " has remainder " in l}
            for a, v in key.items(): ok += got.get(a) == v; wrong += a in got and got[a] != v
        res.setdefault("remainders", {})[c] = {"correct": ok, "wrong": wrong}
        ok = wrong = 0
        for s in range(3):
            lines, bad = worlds.harvest(seed=s)
            stated = {tuple(l.split(" harvests ")) for l in lines if " harvests " in l}
            with tempfile.TemporaryDirectory() as td:
                p = os.path.join(td, "h.txt"); open(p, "w").write("\n".join(lines) + "\n")
                o = eng("\n".join(["SET CONDITIONS 1"] + st) + f"\nINGESTFILE {p}\nRELATIONS\nINFER ALL\nEXIT\n")
            got = {tuple(l.split("\t")[1].split(" harvests ")) for l in o.splitlines() if l.startswith("FACT\t") and " harvests " in l} - stated
            ok += len(got - bad); wrong += len(got & bad)
        res.setdefault("harvest", {})[c] = {"correct": ok, "wrong": wrong}
        print(c, {k: v[c] for k, v in res.items()}, flush=True)
    dump("results_t2.json", res)


def t5():
    rows = []
    for s in (0, 1, 2):
        obs, hid = lib.world("gates", seed=s, per_kind=800, noise=0.0)
        for c, st in (("default_cap", ["SET TREES 1"]), ("maxwords30000", ["SET TREES 1", "SET MAXWORDS 30000"])):
            t = time.time(); out = lib.run(obs, st); r = lib.score(out, obs, hid)
            # hidden non-random outputs: truth 'has value' facts not stated, for outputs of non-random gates
            rels = sorted(hid["relations"], key=len, reverse=True); T = {tuple(x) for x in hid["truth"]}
            stated = lib.facts_of(open(obs).read().splitlines(), rels)
            kind = {a: b for rel, a, b in T if rel == "has kind"}; outg = {a: b for rel, a, b in T if rel == "is output of"}
            target = {f for f in T - stated if f[0] == "has value" and f[1] in outg and kind.get(outg[f[1]]) != "rnd"}
            derived = {lib.parse_fact(l.split("\t")[1], rels) for l in out.splitlines() if l.startswith("FACT\t")}
            got = {f for f in derived if f and f[0] == "has value" and f[1] in {t[1] for t in target}}
            rows.append({"seed": s, "config": c, "limit_line": [l for l in out.splitlines() if l.startswith("[LIMIT]")], "targets": len(target),
                         "recovered": len(got & target), "wrong": len(got - target), "seconds": round(time.time() - t, 1)})
            print(rows[-1], flush=True)
    dump("results_t5.json", rows)


def t6():
    rows = []
    for w, kws in (("company", [dict(scale=1.0, noise=0.0, reports=1), dict(scale=2.0, noise=0.0, reports=1), dict(scale=4.0, noise=0.0, reports=1)]),
                   ("hidden", [dict(scale=1, coverage=0.5, noise=0.03, reports=1), dict(scale=2, coverage=0.5, noise=0.03, reports=1), dict(scale=4, coverage=0.5, noise=0.03, reports=1)])):
        for kw in kws:
            obs, _ = lib.world(w, seed=0, **kw); n = sum(1 for _ in open(obs))
            with tempfile.TemporaryDirectory() as td:
                kb = os.path.join(td, "kb.vtx"); q = "ASK ? is based in ?" if w == "company" else "ASK ? is from ?"
                t = time.time(); eng(f"INGESTFILE {obs}\nRELATIONS\nSAVE {kb}\nEXIT\n"); build = time.time() - t
                t = time.time(); eng(f"LOAD {kb}\n{q}\nEXIT\n"); load_q = time.time() - t
                t = time.time(); eng(f"LOAD {kb}\nINFER ALL\nEXIT\n"); load_all = time.time() - t
                size = os.path.getsize(kb)
            rows.append({"world": w, "params": kw, "facts": n, "build_s": round(build, 2), "load_and_first_query_s": round(load_q, 2),
                         "load_and_infer_all_s": round(load_all, 2), "kb_bytes": size})
            print(rows[-1], flush=True)
    dump("results_t6.json", rows)


ONE_VALUE = {"company": ("is based in", "is on"), "hidden": ("lives in", "works as", "is located in")}


def pipeline_majority(lines, rels, one_value):
    """What a data pipeline would do: per subject of a declared one-value relation, keep the most-reported value
    (all tied values on a tie). Other facts pass through once."""
    count = collections.Counter(); keep = []
    for l in lines:
        f = lib.parse_fact(l, rels)
        if f and f[0] in one_value: count[f] += 1
        else: keep.append(l)
    best = collections.defaultdict(list)
    for (r, a, b), n in count.items(): best[(r, a)].append((n, b))
    for (r, a), vs in best.items():
        top = max(n for n, _ in vs)
        keep += [f"{a} {r} {b}" for n, b in vs if n == top]
    return sorted(set(keep))


def t7():
    rows = []
    for w in ("company", "hidden"):
        for nz in (0.15, 0.30):
            for rp in (3, 5):
                for s in range(5):
                    kw = dict(scale=1.0, noise=nz, reports=rp) if w == "company" else dict(scale=1, coverage=0.5, noise=nz, reports=rp)
                    obs, hid = lib.world(w, seed=s, **kw)
                    rels = sorted(hid["relations"], key=len, reverse=True)
                    r_eng = lib.score(lib.run(obs, ["SET VOTE 1"]), obs, hid)
                    lines = pipeline_majority(open(obs).read().splitlines(), rels, ONE_VALUE[w])
                    with tempfile.TemporaryDirectory() as td:
                        p = os.path.join(td, "f.txt"); open(p, "w").write("\n".join(lines) + "\n")
                        out = lib.run(p, [])
                        r_pipe = lib.score(out, obs, hid)   # scored against what was originally stated (same 'new facts' basis)
                    rows.append({"world": w, "noise": nz, "reports": rp, "seed": s, "engine_vote": {k: r_eng[k] for k in ("derived_new", "correct", "wrong", "precision", "recall")},
                                 "pipeline": {k: r_pipe[k] for k in ("derived_new", "correct", "wrong", "precision", "recall")}})
                    print(w, nz, rp, s, round(r_eng["precision"], 4), round(r_pipe["precision"], 4), round(r_eng["recall"], 3), round(r_pipe["recall"], 3), flush=True)
    dump("results_t7.json", rows)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("t1t3", t1t3), ("t2", t2), ("t5", t5), ("t6", t6), ("t7", t7)):
        if what in ("all", name): fn()
