"""egm: build, query and evaluate EGM knowledge bases.

  egm doctor                                   check the install
  egm extract python NAME=DIR ... -o facts     facts from Python source (no LLM)
  egm build facts.txt ... -o kb.vtx            ingest facts, save a knowledge base
  egm ask KB "PATTERN" [--strict] [--json]     query (? marks the slot to fill)
  egm rules KB                                 learned relations and rules
  egm observe KB --source S --record R ...     add source-aware evidence, save back
  egm run KB script.txt [--save]               raw engine commands, one per line
  egm shell KB                                 interactive session
  egm questions truth.json -o DIR              question set + hidden key from truth
  egm answer KB questions.json -o answers.json scripted solver (no LLM)
  egm score key.json answers.json              exact / F1 per question kind
  egm eval KB key.json                         answer + score in one step
  egm bench facts.txt                          ingest, build and query timings
  egm mcp KB [--writable]                      serve KB to LLM clients over MCP (stdio)

KB is a saved knowledge base (.vtx) or a facts file (.txt), which is ingested on the fly.
"""
import argparse
import json
import os
import statistics
import sys
import time

from . import __version__
from .engine import Engine, find_binary
from .errors import EgmError
from . import bench


# --- helpers ------------------------------------------------------------------------------
def open_kb(path, settings=None):
    if not os.path.exists(path):
        sys.exit(f"egm: {path}: no such file")
    return Engine.open(path, settings=settings)


def explain_empty(engine, pattern):
    return engine.explain(pattern) or "no stated or inferred answer"


def parse_settings(items):
    out = {}
    for s in items or []:
        if "=" not in s:
            sys.exit(f"egm: --set expects KEY=VALUE, got {s}")
        k, v = s.split("=", 1); out[k.upper()] = v
    return out


def dump(obj, path):
    with open(path, "w") as f:
        json.dump(obj, f, indent=1)


# --- commands -----------------------------------------------------------------------------
def cmd_doctor(a):
    print(f"egm {__version__}")
    try:
        b = find_binary()
    except FileNotFoundError as e:
        print(f"engine: MISSING ({e})"); return 1
    import subprocess
    v = subprocess.run([b, "--version"], capture_output=True, text=True).stdout.strip() or "unknown (pre-2.2.1 build)"
    print(f"engine: {b}\nversion: {v}")
    import tempfile
    with tempfile.TemporaryDirectory() as td:   # the self-test writes selftest.vtx2 into its working directory
        st = subprocess.run([b, "--selftest"], capture_output=True, text=True, cwd=td).stdout.strip().splitlines()
    for l in st:
        print(l)
    ok = st and all((" 0" in l) for l in st)
    with Engine() as e:
        for i, (x, y) in enumerate([("a", "b"), ("b", "c"), ("c", "d"), ("x", "y"), ("y", "z")]):
            e.ingest(f"{x} is in {y}")
        t0 = time.perf_counter(); r = e.ask("a is in ?"); dt = (time.perf_counter() - t0) * 1000
    print(f"pipe round trip: {len(r)} answers in {dt:.1f} ms")
    print("status: OK" if ok else "status: CHECK SELFTEST OUTPUT")
    return 0 if ok else 1


def cmd_extract(a):
    if a.language != "python":
        sys.exit("egm: only `python` extraction is built in; write facts as 'A relation B' lines for anything else")
    from .extract_python import extract, write
    for s in a.specs:
        if "=" not in s or not os.path.isdir(s.split("=", 1)[1]):
            sys.exit(f"egm: expected NAME=DIR with an existing directory, got {s}")
    out = a.output[:-4] if a.output.endswith(".txt") else a.output
    counts = write(extract(a.specs), out + ".txt", out + ".truth.json")
    print(f"wrote {out}.txt ({sum(counts.values())} facts) and {out}.truth.json")
    for r, n in counts.items():
        print(f"  {r:15s} {n}")


def cmd_build(a):
    t0 = time.perf_counter()
    with Engine(facts=a.facts, settings=parse_settings(a.set)) as e:
        t1 = time.perf_counter()
        rel = e.cmd("RELATIONS")                  # forces the inference build, so errors surface now
        t2 = time.perf_counter()
        e.save(a.output)
    n = sum(1 for f in a.facts for l in open(f) if l.strip())
    print(f"built {a.output}: {n} lines from {len(a.facts)} file(s); ingest {t1 - t0:.2f} s, inference build {t2 - t1:.2f} s")
    for l in rel:
        if l.strip().startswith("#") or l.strip().startswith("ACCEPT"):
            print(l)


def cmd_ask(a):
    with open_kb(a.kb, parse_settings(a.set)) as e:
        res = []
        for p in a.pattern:
            facts = e.ask(p, strict=a.strict)
            if a.json:
                res.append({"pattern": p, "strict": a.strict, "results": [f.to_dict() for f in facts]})
                continue
            if len(a.pattern) > 1:
                print(f"# {p}")
            for f in facts:
                print(f.raw if a.verbose else _short(f))
            if not facts:
                print(explain_empty(e, p), file=sys.stderr)
        if a.json:
            print(json.dumps(res[0] if len(res) == 1 else res, indent=1))


def _short(f):
    tag = f.status + (f" [{f.tier}]" if f.tier else "") + (f" (per {f.source})" if f.source else "")
    return f"{f.fact}\t{tag}"


def cmd_rules(a):
    with open_kb(a.kb, parse_settings(a.set)) as e:
        for l in e.cmd("RELATIONS"):
            if a.all or not l.strip().startswith("reject"):
                print(l)


def cmd_observe(a):
    facts = list(a.fact or [])
    if a.file:
        facts += [l.strip() for l in open(a.file) if l.strip()]
    if not facts and a.scope == "partial":
        sys.exit("egm: a partial observation needs at least one fact")
    with open_kb(a.kb) as e:
        e.observe(a.source, a.record, a.time, a.revision, a.scope, facts)
        print(f"[OBSERVE] {a.source}/{a.record} t={a.time} rev={a.revision} {a.scope}: {len(facts)} fact(s)")
        dest = a.output or (a.kb if not a.kb.endswith(".txt") else a.kb[:-4] + ".vtx")
        e.save(dest)
    print(f"saved {dest}")


def cmd_run(a):
    with open_kb(a.kb, parse_settings(a.set)) as e:
        for line in open(a.script):
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.strip().upper() == "EXIT":
                break
            print(f"> {line}")
            for l in e.cmd(line):
                print(l)
        if a.save:
            e.save(a.save); print(f"saved {a.save}")


def cmd_shell(a):
    try:
        import readline  # noqa: F401  (line editing where available)
    except ImportError:
        pass
    e = open_kb(a.kb, parse_settings(a.set)) if a.kb else Engine()
    print("egm shell: engine commands (ASK, RELATIONS, OBSERVE, INFER ALL, HELP, ...). Ctrl-D to quit.")
    try:
        while True:
            try:
                line = input("egm> ")
            except EOFError:
                print(); break
            if not line.strip():
                continue
            if line.strip().upper() in ("EXIT", "QUIT"):
                break
            out = e.cmd(line)
            print("\n".join(out))
            if line.upper().startswith("ASK ") and not any(l.startswith("  ") and "no stated" not in l for l in out):
                print(explain_empty(e, line[4:].strip()))
    finally:
        e.close()


def cmd_questions(a):
    truth = json.load(open(a.truth))
    counts = {}
    for s in a.count or []:
        k, v = s.split("="); counts[k] = int(v)
    Q = bench.make_questions(truth, seed=a.seed, counts=counts)
    os.makedirs(a.output, exist_ok=True)
    dump(bench.public(Q), os.path.join(a.output, "questions.json"))
    dump(Q, os.path.join(a.output, "key.json"))
    import collections
    print(f"wrote {len(Q)} questions to {a.output}/questions.json and the key to {a.output}/key.json (seed {a.seed})")
    print("  " + ", ".join(f"{k} {v}" for k, v in collections.Counter(q["kind"] for q in Q).items()))
    print("keep key.json away from any LLM you are evaluating")


def _answer(e, qs, strict):
    t0 = time.perf_counter(); ans = bench.solve(e, qs, strict=strict); return ans, time.perf_counter() - t0


def cmd_answer(a):
    qs = json.load(open(a.questions))
    with open_kb(a.kb, parse_settings(a.set)) as e:
        ans, dt = _answer(e, qs, a.strict)
    dump(ans, a.output)
    print(f"wrote {len(ans)} answers to {a.output} in {dt:.2f} s (policy: {'strict' if a.strict else 'all'})")


def _print_score(r, title=""):
    if title:
        print(title)
    print(f"  questions {r['questions']}   mean F1 {r['mean_f1']:.3f}   exact {r['exact']}/{r['questions']}"
          + (f"   missing {r['missing']}" if r["missing"] else ""))
    for k, v in r["by_kind"].items():
        print(f"  {k:15s} n={v['n']:<3d} F1 {v['mean_f1']:.3f}  exact {v['exact']}/{v['n']}")


def cmd_score(a):
    r = bench.score(json.load(open(a.key)), json.load(open(a.answers)))
    _print_score(r)
    if a.output:
        dump(r, a.output)
    if a.expect is not None and abs(r["mean_f1"] - a.expect) > 1e-9:
        print(f"FAIL: expected mean F1 {a.expect:.3f}"); return 1


def cmd_eval(a):
    key = json.load(open(a.key))
    policies = [False, True] if a.both else [a.strict]
    out = {}
    with open_kb(a.kb, parse_settings(a.set)) as e:
        for strict in policies:
            ans, dt = _answer(e, key, strict)
            r = bench.score(key, ans)
            name = "strict" if strict else "all"
            _print_score(r, f"policy {name}  ({dt:.2f} s, 0 LLM tokens)")
            out[name] = {"seconds": round(dt, 3), **r, "answers": ans}
    if a.output:
        dump(out, a.output); print(f"wrote {a.output}")
    if a.expect is not None:
        got = out["strict" if a.strict and not a.both else "all"]["mean_f1"]
        if abs(got - a.expect) > 1e-9:
            print(f"FAIL: expected mean F1 {a.expect:.3f}, got {got:.3f}"); return 1


def cmd_mcp(a):
    from .mcp_server import run
    return run(a.kb, writable=a.writable, save_path=a.save_to, autosave=a.autosave, settings=parse_settings(a.set))


def cmd_bench(a):
    rows = []
    for path in a.facts:
        n = sum(1 for l in open(path) if l.strip())
        t0 = time.perf_counter()
        with Engine(facts=[path]) as e:
            t1 = time.perf_counter(); e.relations(); t2 = time.perf_counter()
            subj = [l.split()[0] for l in open(path) if l.strip()][: a.queries]
            lat = []
            for s in subj:
                q0 = time.perf_counter(); e.ask(f"{s} calls ?"); lat.append((time.perf_counter() - q0) * 1000)
            kb = "/tmp/egm_bench.vtx"; e.save(kb); size = os.path.getsize(kb)
        rows.append((os.path.basename(path), n, t1 - t0, t2 - t1, statistics.median(lat), max(lat), size, os.path.getsize(path)))
    print(f"{'facts file':22s} {'facts':>6s} {'ingest s':>9s} {'build s':>8s} {'ask p50 ms':>11s} {'ask max ms':>11s} {'kb bytes':>9s} {'txt bytes':>9s}")
    for r in rows:
        print(f"{r[0]:22s} {r[1]:6d} {r[2]:9.2f} {r[3]:8.2f} {r[4]:11.2f} {r[5]:11.2f} {r[6]:9d} {r[7]:9d}")


# --- argument parsing ---------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(prog="egm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"egm {__version__}")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    def add(name, fn, help_):
        s = sub.add_parser(name, help=help_, description=help_); s.set_defaults(fn=fn); return s

    def with_set(s):
        s.add_argument("--set", action="append", metavar="KEY=VALUE", help="engine setting, e.g. RATE=0.4, REFRESH=0.02, DX=1")
        return s

    add("doctor", cmd_doctor, "check the engine binary and run its self-test")
    s = add("extract", cmd_extract, "extract facts from source code without an LLM")
    s.add_argument("language", choices=["python"]); s.add_argument("specs", nargs="+", metavar="NAME=DIR")
    s.add_argument("-o", "--output", required=True, help="output prefix: writes PREFIX.txt and PREFIX.truth.json")
    s = with_set(add("build", cmd_build, "ingest facts files and save a knowledge base"))
    s.add_argument("facts", nargs="+"); s.add_argument("-o", "--output", required=True)
    s = with_set(add("ask", cmd_ask, "query a knowledge base"))
    s.add_argument("kb"); s.add_argument("pattern", nargs="+", help='e.g. "? calls requests__select_proxy" (quote it)')
    s.add_argument("--strict", action="store_true", help="stated facts and law-tier inferences only")
    s.add_argument("--json", action="store_true"); s.add_argument("-v", "--verbose", action="store_true", help="show proofs")
    s = with_set(add("rules", cmd_rules, "show learned relations and accepted rules"))
    s.add_argument("kb"); s.add_argument("--all", action="store_true", help="include rejected candidate rules")
    s = add("observe", cmd_observe, "add a source-aware observation and save the knowledge base")
    s.add_argument("kb"); s.add_argument("--source", required=True); s.add_argument("--record", required=True)
    s.add_argument("--time", type=int, required=True); s.add_argument("--revision", type=int, default=1)
    s.add_argument("--scope", choices=["snapshot", "partial"], default="snapshot",
                   help="snapshot: this is everything the record says now; partial: facts to add")
    s.add_argument("-f", "--fact", action="append", help="one fact, repeatable"); s.add_argument("--file", help="facts, one per line")
    s.add_argument("-o", "--output", help="save here instead of overwriting KB")
    s = with_set(add("run", cmd_run, "run raw engine commands from a file"))
    s.add_argument("kb"); s.add_argument("script"); s.add_argument("--save", metavar="KB_OUT")
    s = with_set(add("shell", cmd_shell, "interactive engine session"))
    s.add_argument("kb", nargs="?")
    s = add("questions", cmd_questions, "generate a question set and hidden key from extractor truth")
    s.add_argument("truth"); s.add_argument("-o", "--output", required=True, help="output directory")
    s.add_argument("--seed", type=int, default=2026)
    s.add_argument("--count", action="append", metavar="KIND=N", help=f"questions per kind ({', '.join(bench.KINDS)})")
    s = with_set(add("answer", cmd_answer, "answer a question set with the scripted solver (no LLM)"))
    s.add_argument("kb"); s.add_argument("questions"); s.add_argument("-o", "--output", required=True)
    s.add_argument("--strict", action="store_true")
    s = add("score", cmd_score, "score answers against a key")
    s.add_argument("key"); s.add_argument("answers"); s.add_argument("-o", "--output")
    s.add_argument("--expect", type=float, help="exit 1 unless mean F1 equals this (for CI)")
    s = with_set(add("eval", cmd_eval, "answer and score in one step"))
    s.add_argument("kb"); s.add_argument("key"); s.add_argument("--strict", action="store_true")
    s.add_argument("--both", action="store_true", help="run the all and strict policies")
    s.add_argument("-o", "--output"); s.add_argument("--expect", type=float, help="exit 1 unless mean F1 equals this (for CI)")
    s = with_set(add("mcp", cmd_mcp, "serve a knowledge base over MCP (stdio) to LLM clients"))
    s.add_argument("kb", help="a saved knowledge base (.vtx) or a facts file (.txt)")
    s.add_argument("--writable", action="store_true", help="also expose egm_observe, egm_ingest and egm_save")
    s.add_argument("--save-to", metavar="PATH", help="where egm_save writes (default: KB, or KB.vtx for a .txt)")
    s.add_argument("--autosave", action="store_true", help="with --writable: save unsaved additions on exit")
    s = add("bench", cmd_bench, "time ingest, inference build and queries")
    s.add_argument("facts", nargs="+"); s.add_argument("--queries", type=int, default=50)

    a = p.parse_args(argv)
    if not a.command:
        p.print_help(); return 0
    try:
        return a.fn(a) or 0
    except (EgmError, FileNotFoundError, ValueError) as e:
        print(f"egm: {e}", file=sys.stderr); return 2
    except BrokenPipeError:
        return 0
