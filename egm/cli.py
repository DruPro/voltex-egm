"""egm: build, query and evaluate EGM knowledge bases.

  egm doctor                                   check the install
  egm extract python NAME=DIR ... -o facts     facts from Python source (no LLM)
  egm build facts.txt ... -o kb.vtx            ingest facts, save a knowledge base
  egm ask KB "PATTERN" [--strict] [--json]     query (? marks the slot to fill); --policy NAME[@V] runs it under a policy
  egm infer KB [--policy NAME[@V]] [--json]    every derived fact, under a policy (default legacy)
  egm policy list|show|create|configure|clone|versions|export|import|compare   custom inference policies
  egm rules KB                                 learned relations and rules
  egm evidence KB [--all] [--policy NAME[@V]]  each rule's evidence vector (docs/EVIDENCE.md)
  egm observe KB --source S --record R ...     add source-aware evidence, save back
  egm run KB script.txt [--save]               raw engine commands, one per line
  egm shell KB                                 interactive session
  egm questions truth.json -o DIR              question set + hidden key from truth
  egm answer KB questions.json -o answers.json scripted solver (no LLM)
  egm score key.json answers.json              exact / F1 per question kind
  egm eval KB key.json                         answer + score in one step
  egm bench facts.txt                          ingest, build and query timings
  egm tune facts.txt [-o tuned.json]           pick settings for this dataset (holdout; --labels for verified facts; --expanded)
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
from . import policy as _policy


# --- helpers ------------------------------------------------------------------------------
def open_kb(path, settings=None):
    if not os.path.exists(path):
        sys.exit(f"egm: {path}: no such file")
    return Engine.open(path, settings=settings)


def explain_empty(engine, pattern):
    return engine.explain(pattern) or "no stated or inferred answer"


def parse_settings(items, files=None):
    out = {}
    for path in files or []:
        with open(path) as fh:
            d = json.load(fh)
        out.update({k.upper(): v for k, v in d.get("settings", d).items()})
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
    with Engine(facts=a.facts, settings=parse_settings(a.set, getattr(a, 'settings', None))) as e:
        t1 = time.perf_counter()
        rel = e.cmd("RELATIONS")                  # forces the inference build, so errors surface now
        t2 = time.perf_counter()
        e.save(a.output)
    n = sum(1 for f in a.facts for l in open(f) if l.strip())
    print(f"built {a.output}: {n} lines from {len(a.facts)} file(s); ingest {t1 - t0:.2f} s, inference build {t2 - t1:.2f} s")
    for l in rel:
        if l.strip().startswith("#") or l.strip().startswith("ACCEPT"):
            print(l)


def _registry(a):
    return _policy.PolicyRegistry(getattr(a, "policy_dir", None))


def cmd_ask(a):
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
        if a.policy:
            e.apply_policy(a.policy, _registry(a))
        res = []
        for p in a.pattern:
            facts = e.ask(p, strict=a.strict)
            if a.json:
                res.append({"pattern": p, "strict": a.strict, "policy": e.policy.id, "results": [f.to_dict() for f in facts]})
                continue
            if len(a.pattern) > 1:
                print(f"# {p}")
            for f in facts:
                print(f.raw if a.verbose else _short(f))
            if not facts:
                print(explain_empty(e, p), file=sys.stderr)
        if a.json:
            print(json.dumps(res[0] if len(res) == 1 else res, indent=1))


def cmd_infer(a):
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
        pol = e.apply_policy(a.policy or "legacy", _registry(a))
        facts = e.infer_all(); snap = e.snapshot()
        if a.json:
            print(json.dumps({"policy": pol.id, "snapshot": snap, "facts": [f.to_dict() for f in facts]}, indent=1)); return
        print(f"# policy {pol.id}  snapshot {snap}  {len(facts)} derived facts")
        for f in facts:
            print(f"{f.fact}\t{f.tier}")


# --- policies (egm/policy.py is the one implementation; this is its command line) ---------
def _value(v):
    lv = v.lower()
    if lv in ("true", "false"):
        return lv == "true"
    if lv in ("none", "null"):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def _policy_sets(items):
    """--set SECTION.FIELD=VALUE (or extension.SECTION.FIELD=VALUE) -> nested dict. shapes take a comma list."""
    out = {}
    for it in items or []:
        if "=" not in it:
            raise _policy.PolicyError(f"--set expects SECTION.FIELD=VALUE, got {it!r}")
        path, v = it.split("=", 1); keys = path.split(".")
        if len(keys) not in (2, 3) or (len(keys) == 3 and keys[0] != "extension"):
            raise _policy.PolicyError(f"--set expects SECTION.FIELD or extension.SECTION.FIELD, got {path!r}")
        d = out
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = [x for x in v.split(",") if x] if keys[-1] == "shapes" else _value(v)
    return out


def cmd_policy(a):
    reg = _registry(a); act = a.action
    if act == "list":
        for p in reg.list():
            tag = "built-in" if p["builtin"] else f"v{p['version']}"
            print(f"{p['name']}\t{tag}\t{p['description']}")
    elif act == "show":
        print(json.dumps(reg.get(a.name).to_dict(), indent=1))
    elif act == "versions":
        if a.name in _policy.BUILTINS:
            print(f"{_policy.BUILTINS[a.name].version} (built-in)")
        else:
            vs = reg.versions(a.name)
            if not vs:
                raise _policy.PolicyError(f"no policy named {a.name!r}")
            print(" ".join(str(v) for v in vs))
    elif act in ("create", "configure"):
        cfg = {}
        if getattr(a, "from_json", None):
            with open(a.from_json) as fh:
                cfg = {k: v for k, v in json.load(fh).items() if k in ("thresholds", "validation", "inference", "extension")}
        sets = _policy_sets(a.set)
        for k, v in sets.items():
            cfg.setdefault(k, {}).update(v) if isinstance(v, dict) else cfg.__setitem__(k, v)
        if act == "create":
            p = reg.create(a.name, cfg.get("thresholds"), cfg.get("validation"), cfg.get("inference"), cfg.get("extension"),
                           a.description or "")
        else:
            ext = None if a.no_extension else cfg.get("extension", False)
            p = reg.update(a.name, cfg.get("thresholds"), cfg.get("validation"), cfg.get("inference"), ext, a.description)
        print(f"{p.id}"); print(json.dumps(p.to_dict(), indent=1))
    elif act == "clone":
        print(reg.clone(a.source, a.name).id)
    elif act == "export":
        d = reg.export(a.name, a.output)
        if not a.output:
            print(json.dumps(d, indent=1))
    elif act == "import":
        print(reg.import_(a.file, a.name).id)
    elif act == "compare":
        with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
            c = e.compare_policies(a.policies, reg)
        if a.json:
            print(json.dumps(c.to_dict(), indent=1)); return
        print(f"# snapshot {c.snapshot}")
        print("policy\tderived\tcore\textension\trules core\trules extension\trules accepted")
        for r in c.summary:
            print(f"{r['policy']}\t{r['derived']}\t{r['core']}\t{r['extension']}\t{r['rules_core']}\t{r['rules_extension']}\t{r['rules_accepted']}")
        for k, v in c.contained.items():
            print(f"{k}: {'yes' if v else 'no'}")


def _short(f):
    tag = f.status + (f" [{f.tier}]" if f.tier else "") + (f" (per {f.source})" if f.source else "")
    return f"{f.fact}\t{tag}"


def cmd_rules(a):
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
        for l in e.cmd("RELATIONS"):
            if a.all or not l.strip().startswith("reject"):
                print(l)


EV_COLS = ("admit", "tier", "n", "e_plus", "e_minus", "agree", "rel", "cov", "cov_source", "stability", "validation")


def cmd_evidence(a):
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
        pol = e.apply_policy(a.policy or "legacy", _registry(a))
        ev = e.evidence(include_rejected=a.all)
        if a.json:
            print(json.dumps({"policy": pol.id, "snapshot": e.snapshot(), "rules": ev}, indent=1)); return
        print(f"# policy {pol.id}  {len(ev)} rules" + ("" if a.all else " (accepted; --all for every candidate)"))
        print("\t".join(("accepted",) + EV_COLS + ("rule",)))
        f = lambda v: "undef" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
        for r in ev:
            print("\t".join([("yes" if r["accepted"] else "no")] + [f(r.get(c)) for c in EV_COLS] + [r["rule"]]))


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
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
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
    e = open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) if a.kb else Engine()
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
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
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
    with open_kb(a.kb, parse_settings(a.set, getattr(a, 'settings', None))) as e:
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


def cmd_tune(a):
    from .tune import DEFAULT_SPACE, expanded_space, tune
    full = expanded_space(a.facts) if a.expanded else DEFAULT_SPACE
    space = full
    if a.only:
        want = {x.strip().upper() for x in a.only.split(",")}
        unknown = want - {k for k, _ in full}
        if unknown:
            sys.exit(f"egm tune: not in the search space: {', '.join(sorted(unknown))}")
        space = [(k, v) for k, v in full if k in want]
    labels = None
    if a.labels:
        with open(a.labels) as fh:
            labels = [l.strip() for l in fh if l.strip()]
    try:
        r = tune(a.facts, folds=a.folds, holdout=a.holdout, space=space, min_gain=a.min_gain, sweeps=a.sweeps,
                 seed=a.seed, labels=labels, progress=None if a.quiet else print,
                 settings=parse_settings(a.set, a.settings) or None)
    except ValueError as e:
        sys.exit(f"egm tune: {e}")
    print(r.report())
    if a.output:
        dump({"settings": r.all_settings, "baseline": r.baseline, "tuned": r.tuned, "baseline_folds": r.baseline_folds,
              "tuned_folds": r.tuned_folds, "mode": r.mode, "evaluations": r.evaluations, "history": r.history}, a.output)
        print(f"wrote {a.output}: use it with  egm build {a.facts} -o kb.vtx --settings {a.output}")


def cmd_mcp(a):
    from .mcp_server import run
    return run(a.kb, writable=a.writable, save_path=a.save_to, autosave=a.autosave, settings=parse_settings(a.set, getattr(a, 'settings', None)))


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
        s.add_argument("--settings", action="append", metavar="FILE", help="settings from a JSON file, e.g. the output of egm tune")
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
    s.add_argument("--policy", metavar="NAME[@V]", help="run under this inference policy (egm policy list)")
    s.add_argument("--policy-dir", help="policy registry (default $EGM_POLICY_DIR or ~/.egm/policies)")
    s = with_set(add("infer", cmd_infer, "every derived fact, under an inference policy"))
    s.add_argument("kb"); s.add_argument("--policy", metavar="NAME[@V]", help="default legacy")
    s.add_argument("--policy-dir"); s.add_argument("--json", action="store_true")
    s = with_set(add("evidence", cmd_evidence, "each learned rule's evidence vector (docs/EVIDENCE.md)"))
    s.add_argument("kb"); s.add_argument("--all", action="store_true", help="include rejected candidates")
    s.add_argument("--policy", metavar="NAME[@V]", help="show which stratum admits each rule (default legacy)")
    s.add_argument("--policy-dir"); s.add_argument("--json", action="store_true")
    s = add("policy", cmd_policy, "create, configure, inspect, version, export, import and compare inference policies")
    s.add_argument("--policy-dir", help="policy registry (default $EGM_POLICY_DIR or ~/.egm/policies)")
    ps = s.add_subparsers(dest="action", metavar="ACTION", required=True)
    ps.add_parser("list", help="built-in and custom policies")
    x = ps.add_parser("show", help="a policy's full configuration"); x.add_argument("name", metavar="NAME[@V]")
    x = ps.add_parser("versions", help="a custom policy's versions"); x.add_argument("name")
    for act, hlp in (("create", "a new policy (version 1)"), ("configure", "a new version of a custom policy")):
        x = ps.add_parser(act, help=hlp); x.add_argument("name")
        x.add_argument("--set", action="append", metavar="SECTION.FIELD=VALUE",
                       help="e.g. thresholds.minAgreement=0.9, validation.required=true, validation.split=blocked, "
                            "inference.maxDepth=2, inference.shapes=inverse,chain, extension.thresholds.minSampleSize=0")
        x.add_argument("--from-json", metavar="FILE", help="configuration from a JSON file (as export writes it)")
        x.add_argument("--description")
        if act == "configure":
            x.add_argument("--no-extension", action="store_true", help="remove the extension stratum")
    x = ps.add_parser("clone", help="copy a policy under a new name"); x.add_argument("source", metavar="NAME[@V]"); x.add_argument("name")
    x = ps.add_parser("export", help="write a policy's configuration as JSON"); x.add_argument("name", metavar="NAME[@V]")
    x.add_argument("-o", "--output")
    x = ps.add_parser("import", help="a policy from JSON (new policy, or the next version)"); x.add_argument("file")
    x.add_argument("--name")
    x = with_set(ps.add_parser("compare", help="run policies on the same knowledge base and compare"))
    x.add_argument("kb"); x.add_argument("policies", nargs="+", metavar="NAME[@V]"); x.add_argument("--json", action="store_true")
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
    s = add("tune", cmd_tune, "pick settings for one dataset from the dataset itself")
    s.add_argument("facts"); s.add_argument("-o", "--output", help="write the chosen settings and the full search log (JSON)")
    s.add_argument("--labels", help="verified facts, one per line: score on these instead of hidden stated facts")
    s.add_argument("--folds", type=int, default=3); s.add_argument("--holdout", type=float, default=0.15)
    s.add_argument("--min-gain", type=float, default=0.005); s.add_argument("--sweeps", type=int, default=2)
    s.add_argument("--only", help="comma-separated settings to search (default: all in egm.tune.DEFAULT_SPACE)")
    s.add_argument("--seed", type=int, default=0); s.add_argument("-q", "--quiet", action="store_true")
    s.add_argument("--expanded", action="store_true",
                   help="also search TENDENCYSTEPS, DEPTH 1/2 and a data-sized MAXWORDS (about 2.6x slower; egm.tune.expanded_space)")
    with_set(s)   # --set / --settings: the base configuration tuning starts from
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


if __name__ == "__main__":
    main()
