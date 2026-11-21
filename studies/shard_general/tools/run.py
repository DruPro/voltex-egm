"""Harness for studies/shard_general: does sharding work on every world, with a split derived from the data?

Arms: single (one engine), A (split.auto), R (split.random), U (user-named split; company only). Every sharded arm
runs through egm.shard with consensus on and central off (its defaults). The split is passed in by replacing
egm.shard's internal _assign for the duration of the call; nothing else in egm.shard changes. Every engine gets
CLUSTERSTREAM 1 (identical answers, less memory) plus the world's settings.

Usage: python3 run.py PART    PART in pilot | confirm     appends to ../results_PART.jsonl
"""
import contextlib, hashlib, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
STUDY = os.path.abspath(os.path.join(HERE, ".."))
sys.path[:0] = [HERE, ROOT, os.path.join(ROOT, "studies", "shard", "tools"), os.path.join(ROOT, "studies", "noise", "tools"),
                os.path.join(STUDY, "hidden")]
import egm                       # noqa: E402
import split                     # noqa: E402  (facts only)
import shard as study_shard      # noqa: E402  run_engine (wait4 peak RSS), maxwords_for
import lib                       # noqa: E402  scorer
import worlds                    # noqa: E402  generators (hidden truth)
SHARD_MOD = sys.modules["egm.shard"]
BINARY = egm.find_binary()
OBS, HID = os.path.join(STUDY, "obs"), os.path.join(STUDY, "hidden", "cache")
SETTINGS = {"gates": {"TREES": 1}, "lineage": {"CHAIN": 3},
            "realcode": {"COVERAGE": 0}}   # pilot: with defaults one engine passed 18 GB (coverage-scaled reliability; see RESULTS)
USER_SPLIT = {"company": dict(graph=["collaborates with"], attach=["works under"])}


def world(name, **kw):
    tag = name + "_" + "_".join(f"{k}{v}" for k, v in sorted(kw.items()))
    obs, hid = os.path.join(OBS, tag + ".txt"), os.path.join(HID, tag + ".json")
    if not (os.path.exists(obs) and os.path.exists(hid)):
        lines, h = worlds.WORLDS[name](**kw)
        os.makedirs(OBS, exist_ok=True); os.makedirs(HID, exist_ok=True)
        open(obs, "w").write("\n".join(lines) + "\n"); json.dump(h, open(hid, "w"))
    return obs, json.load(open(hid)), tag


def score(answers, obs, hidden):
    text = "\n".join(f"FACT\t{f}\t{t}" for f, t in sorted(answers.items()))
    r = lib.score(text, obs, hidden)
    d = {k: r[k] for k in ("stated", "derived_new", "correct", "wrong", "precision", "recall")}
    d["answers_sha"] = hashlib.sha256("\n".join(sorted(answers)).encode()).hexdigest()[:16]
    return d


@contextlib.contextmanager
def assignment(shard_of):
    old = SHARD_MOD._assign
    SHARD_MOD._assign = lambda *a, **k: dict(shard_of)
    try: yield
    finally: SHARD_MOD._assign = old


def one(name, kw, arm, n, single_answers):
    obs, hid, tag = world(name, **kw)
    lines = [l for l in open(obs).read().splitlines() if l.strip()]
    st = {"CLUSTERSTREAM": 1, **SETTINGS.get(name, {})}
    base = dict(world=name, params=kw, tag=tag, arm=arm, n=n, input_facts=len(lines))
    if arm == "single":
        out, info = study_shard.run_engine(BINARY, obs, {"MAXWORDS": study_shard.maxwords_for(lines), **st}, rss_limit_kb=18 * 1024 * 1024)
        if info["exit"] != 0 or info["killed"]: return {**base, "completed": False, **info}, None
        ans = {}
        for f, t in study_shard.facts_out(out): ans.setdefault(f, t)
        info["limit_lines"] = len(info["limit_lines"])
        return {**base, "completed": True, **info, **score(ans, obs, hid)}, ans
    t = time.time()
    if arm == "U":
        r = egm.shard(obs, n, settings=st, **USER_SPLIT[name])
        shard_of = None
    else:
        shard_of = split.auto(lines, n) if arm == "A" else split.random(lines, n)
        with assignment(shard_of):
            r = egm.shard(obs, n, key="__assigned__", settings=st)
    sec = round(time.time() - t, 3)
    ans = {f.fact: f.tier for f in r.facts}
    rep = r.report
    shard_facts = [e["facts"] for e in rep["engines"] if e["name"].startswith("shard")]
    ents = {x for l in lines for x in (l.split()[0], l.split()[-1])}
    d = {**base, "completed": True, "seconds": sec, "engine_seconds": rep["seconds"], "warnings": r.warnings,
         "shard_facts": shard_facts, "duplication": round(sum(shard_facts) / len(lines), 3),
         "reference_facts": rep.get("reference_facts"), "unseen_facts": rep.get("unseen_facts"),
         "assigned_share": round(len(shard_of) / len(ents), 4) if shard_of is not None else None,
         "consensus_dropped": rep.get("consensus_dropped"), "minority_rules": len(rep.get("minority_rules", [])),
         **score(ans, obs, hid)}
    if single_answers is not None:
        a, b = set(ans), set(single_answers)
        d.update(jaccard_vs_single=round(len(a & b) / len(a | b), 4) if a | b else 1.0,
                 identical_to_single=a == b and all(ans[f] == single_answers[f] for f in a),
                 missing_vs_single=len(b - a), extra_vs_single=len(a - b))
    return d, ans


def cells(part):
    if part == "pilot":   # seed 9, small sizes: checks the harness runs end to end; exploratory
        W = [("company", dict(seed=9, scale=2, noise=0.0)), ("company", dict(seed=9, scale=2, noise=0.15)),
             ("blind", dict(seed=9, scale=1)), ("gates", dict(seed=9, per_kind=200)),
             ("lineage", dict(seed=9, families=120)), ("realcode", dict(seed=9, hide=0.2))]
        for w in W: yield w, (2,)
    if part == "confirm":
        for s in (0, 1, 2):
            for w in [("company", dict(seed=s, scale=16, noise=0.0)), ("company", dict(seed=s, scale=16, noise=0.15)),
                      ("blind", dict(seed=s, scale=8)), ("gates", dict(seed=s, per_kind=1600)),
                      ("lineage", dict(seed=s, families=600)), ("realcode", dict(seed=s, hide=0.2))]:
                yield w, (4, 8)


def main():
    part = sys.argv[1]
    out = os.path.join(STUDY, f"results_{part}.jsonl")
    done = {}
    if os.path.exists(out):
        for l in open(out): d = json.loads(l); done[(d["tag"], d["arm"], d["n"])] = d
    with open(out, "a") as f:
        for (name, kw), ns in cells(part):
            obs, hid, tag = world(name, **kw)
            rs, single = one(name, kw, "single", None, None) if (tag, "single", None) not in done else (None, None)
            if rs: f.write(json.dumps(rs) + "\n"); f.flush(); print(tag, "single", rs.get("precision"), rs.get("recall"), rs.get("cpu"), rs.get("rss_mb"), flush=True)
            if single is None:   # resumed: recompute the single engine's answers (deterministic) for the agreement columns
                _, single = one(name, kw, "single", None, None)
            for n in ns:
                for arm in (["A", "R"] + (["U"] if name in USER_SPLIT else [])):
                    if (tag, arm, n) in done: continue
                    d, _ = one(name, kw, arm, n, single)
                    f.write(json.dumps(d) + "\n"); f.flush()
                    print(tag, arm, n, {k: d.get(k) for k in ("precision", "recall", "wrong", "jaccard_vs_single", "identical_to_single",
                                                              "duplication", "assigned_share", "consensus_dropped", "seconds")}, d["warnings"][:1], flush=True)


if __name__ == "__main__":
    main()
