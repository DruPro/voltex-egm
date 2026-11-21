"""Scaling audit (descriptive). Profiles each engine stage across sizes and world shapes with the instrumented lab copy
(lab/voltex2_lab, PROFILE 2 prints extra [LAB] lines; with PROFILE 0 it must equal the frozen engine, see gate.py).

Usage: python3 audit.py PART   PART in stages | incremental
Appends JSON lines to ../results_audit_PART.jsonl.
"""
import json, os, re, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "shard", "tools"))
sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "tools"))
import shard   # noqa: E402  run_engine (wait4 peak RSS), maxwords_for
import lib     # noqa: E402  generator access
STUDY = os.path.abspath(os.path.join(HERE, ".."))
LAB = os.environ.get("LAB", os.path.join(STUDY, "lab", "voltex2_lab"))
OBS = os.path.join(STUDY, "obs")


def world(name, **kw):
    tag = name + "_" + "_".join(f"{k}{v}" for k, v in sorted(kw.items()))
    p = os.path.join(OBS, tag + ".txt")
    if not os.path.exists(p):
        lines, _ = lib.gen.WORLDS[name](**kw)       # the truth is discarded: this audit measures cost, not accuracy
        os.makedirs(OBS, exist_ok=True); open(p, "w").write("\n".join(lines) + "\n")
    return p, tag


def parse(out):
    r = {"lab_rounds": []}
    m = re.search(r"\[INGEST\] (\d+) records, (\d+) bytes in ([\d.]+) s", out)
    if m: r.update(records=int(m.group(1)), bytes=int(m.group(2)), ingest_s=float(m.group(3)))
    m = re.search(r"\[PROFILE\] classes ([\d.]+) ms \| relations ([\d.]+) ms \| rule mining ([\d.]+) ms", out)
    if m: r.update(classes_ms=float(m.group(1)), relations_ms=float(m.group(2)), mining_ms=float(m.group(3)))
    m = re.search(r"\[PROFILE\] infer ([\d.]+) ms, (\d+) rounds", out)
    if m: r.update(infer_ms=float(m.group(1)), infer_rounds=int(m.group(2)))
    for k in ("before classes", "after classes", "after relations", "after rule mining"):
        m = re.search(rf"\[LAB\] rss {k} ([\d.]+) MB", out)
        if m: r["rss_" + k.replace(" ", "_")] = float(m.group(1))
    m = re.search(r"\(words (\d+)\)", out)
    if m: r["vocab"] = int(m.group(1))
    for m in re.finditer(r"\[LAB\] classes round (\d+): K=(\d+) cosine pairs=(\d+) kept=(\d+) kept_MB=([\d.]+) rss_MB=([\d.]+) ms=([\d.]+)", out):
        r["lab_rounds"].append(dict(round=int(m.group(1)), K=int(m.group(2)), cos=int(m.group(3)), kept=int(m.group(4)),
                                    kept_mb=float(m.group(5)), rss_mb=float(m.group(6)), ms=float(m.group(7))))
    m = re.search(r"Grammar:\s+(\d+) rules, (\d+) symbols", out)
    if m: r.update(grammar_rules=int(m.group(1)), grammar_symbols=int(m.group(2)))
    m = re.search(r"Count tables:\s+(\d+) bigrams, (\d+) trigrams", out)
    if m: r.update(bigrams=int(m.group(1)), trigrams=int(m.group(2)))
    m = re.search(r"Process RSS:\s+([\d.]+) MB", out)
    if m: r["rss_end"] = float(m.group(1))
    r["derived"] = sum(1 for l in out.splitlines() if l.startswith("FACT\t"))
    r["limit_lines"] = sum(1 for l in out.splitlines() if l.startswith("[LIMIT]"))
    return r


def stage_cells():
    for s in (0, 1):
        for x in (1, 2, 4, 8, 16, 32, 64): yield "company", dict(seed=s, scale=x, noise=0.0)
        for x in (1, 2, 4, 8): yield "hidden", dict(seed=s, scale=x, coverage=0.5, noise=0.03)
        for pk in (200, 400, 800, 1600, 2400): yield "gates", dict(seed=s, per_kind=pk, noise=0.0)


def run_stages(out_path, done):
    with open(out_path, "a") as f:
        for name, kw in stage_cells():
            p, tag = world(name, **kw)
            if tag in done: continue
            lines = open(p).read().splitlines()
            st_in = {"PROFILE": 2, "MAXWORDS": shard.maxwords_for(lines)}
            if name == "gates": st_in["TREES"] = 1
            out, st = shard.run_engine(LAB, p, st_in, rss_limit_kb=18 * 1024 * 1024, extra=["METRICS"])
            st["limit_lines"] = len(st["limit_lines"])
            r = {"world": name, "params": kw, "tag": tag, "facts": len(lines), "settings": st_in, **st, **parse(out)}
            f.write(json.dumps(r) + "\n"); f.flush()
            print(tag, r["facts"], "wall", r["seconds"], "rss", r["rss_mb"], "ingest", r.get("ingest_s"), "classes", r.get("classes_ms"),
                  "rel", r.get("relations_ms"), "mine", r.get("mining_ms"), "infer", r.get("infer_ms"),
                  "rounds", [(x["K"], x["kept"], x["kept_mb"]) for x in r["lab_rounds"]], flush=True)


def run_incremental(out_path, done):
    """Time to an answer for the ways facts arrive: cold build, reopening a saved KB, and adding one fact to a live session
    (a fact with known words, a fact with a new name), with REFRESH 0 (default) and 0.02. Uses the frozen engine's
    protocol through the SDK (ECHO-delimited replies); every timing is wall-clock around one command."""
    sys.path.insert(0, ROOT)
    import egm
    with open(out_path, "a") as f:
        for s in (0, 1):
            for x in (4, 8, 16, 32):
                for refresh in (0, 0.02):
                    p, tag = world("company", seed=s, scale=x, noise=0.0)
                    tag = f"{tag}_refresh{refresh}"
                    if tag in done: continue
                    lines = open(p).read().splitlines()
                    person = next(l.split()[0] for l in lines if " is on " in l)
                    team = next(l.split()[-1] for l in lines if l.startswith(person + " is on "))
                    q = f"ASK {person} is based in ?"
                    r = {"world": "company", "params": dict(seed=s, scale=x), "tag": tag, "facts": len(lines), "refresh": refresh}
                    e = egm.Engine(binary=LAB, settings={"MAXWORDS": shard.maxwords_for(lines), "REFRESH": refresh})
                    T = lambda c: (lambda t: (e.cmd(c), round(time.perf_counter() - t, 3))[1])(time.perf_counter())
                    r["ingestfile_s"] = T(f"INGESTFILE {p}")
                    r["first_answer_s"] = T(q)                      # full build + inference
                    r["repeat_answer_s"] = T(q)
                    kb = os.path.join(tempfile.mkdtemp(prefix="scal_"), "kb.vtx")
                    r["save_s"] = T(f"SAVE {kb}"); r["kb_bytes"] = os.path.getsize(kb)
                    r["known_words_ingest_s"] = T(f"INGEST {person} likes {'pizza' if 'pizza' not in team else 'soup'}")
                    r["known_words_answer_s"] = T(q)
                    r["new_name_ingest_s"] = T(f"INGEST zzqnewperson is on {team}")
                    r["new_name_answer_s"] = T(q)
                    r["builds"] = [l for l in e.cmd("METRICS") if "RSS" in l]
                    e.close()
                    e = egm.Engine(binary=LAB, settings={"MAXWORDS": shard.maxwords_for(lines), "REFRESH": refresh})
                    r["load_s"] = T(f"LOAD {kb}")
                    r["after_load_answer_s"] = T(q)
                    e.close(); os.unlink(kb)
                    f.write(json.dumps(r) + "\n"); f.flush()
                    print(tag, {k: v for k, v in r.items() if k.endswith("_s")}, flush=True)


def main():
    part = sys.argv[1]
    out = os.path.join(STUDY, f"results_audit_{part}.jsonl")
    done = {json.loads(l)["tag"] for l in open(out)} if os.path.exists(out) else set()
    if part == "stages": run_stages(out, done)
    elif part == "incremental": run_incremental(out, done)
    else: raise SystemExit("unknown part")


if __name__ == "__main__":
    main()
