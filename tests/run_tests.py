"""EGM kit tests. Groups: engine, cli, repro.   python3 tests/run_tests.py --egm bin/egm [--only engine,repro]

engine  the binary itself: self-test, determinism, SAVE/LOAD equivalence, piped sessions
cli     every egm command on a small generated package, end to end
repro   the published numbers (Requests use case and tokenomics study), exactly
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EX = os.path.join(ROOT, "examples")
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not cond else ""))


def egm(*args, expect=0):
    r = subprocess.run([sys.executable, EGM, *args], capture_output=True, text=True)
    if expect is not None and r.returncode != expect:
        print(r.stdout[-2000:], r.stderr[-2000:])
    return r


def engine_bin():
    return os.environ.get("VOLTEX") or os.path.join(ROOT, "build", "voltex2")


def run_engine(script):
    return subprocess.run([engine_bin()], input=script, capture_output=True, text=True).stdout


# --- engine ---------------------------------------------------------------------------------
def t_engine(tmp):
    print("engine")
    st = subprocess.run([engine_bin(), "--selftest"], capture_output=True, text=True).stdout
    check("self-test: round trip, identity, SAVE/LOAD, grammar invariants", st.count(": 0") >= 3 and " 0 duplicate pairs, 0 under-used" in st, st)
    facts = os.path.join(EX, "tokenomics", "M.txt")
    q = "ASK ? calls requests__select_proxy\nASK requests__sessions imports ?\nRELATIONS\n"
    a = run_engine(f"INGESTFILE {facts}\n{q}EXIT\n"); b = run_engine(f"INGESTFILE {facts}\n{q}EXIT\n")
    strip = lambda s: "\n".join(l for l in s.splitlines() if not l.startswith(("[INGEST", "[LOAD", "[SAVE")))   # timing lines vary
    check("same input gives identical answers, rules and scores", strip(a) == strip(b) and len(a) > 1000)
    kb = os.path.join(tmp, "m.vtx")
    run_engine(f"INGESTFILE {facts}\nSAVE {kb}\nEXIT\n")
    c = run_engine(f"LOAD {kb}\n{q}EXIT\n")
    check("LOAD gives the same answers as ingesting", strip(a) == strip(c))
    sys.path.insert(0, ROOT)
    from egm.engine import Engine
    with Engine(facts=[facts]) as e:
        n1 = len(e.ask("requests__sessions imports ?")); t0 = time.perf_counter()
        for _ in range(200):
            e.ask("? calls requests__select_proxy")
        dt = (time.perf_counter() - t0) / 200 * 1000
        n2 = len(e.ask("requests__sessions imports ?"))
    check("persistent session: repeated queries stable", n1 == n2 and n1 > 0)
    check(f"persistent session: query latency under 20 ms (got {dt:.2f} ms)", dt < 20)


# --- cli ------------------------------------------------------------------------------------
PKG = {
    "__init__.py": "",
    "errors.py": """
        class BaseError(Exception): pass
        class NetError(BaseError): pass
        class TimeoutErr(NetError): pass
        class AuthError(BaseError): pass
        """,
    "net.py": """
        from .errors import NetError, TimeoutErr
        def connect(h):
            if not h: raise NetError()
            return open_socket(h)
        def open_socket(h):
            raise TimeoutErr()
        def fetch(u):
            return connect(u)
        def retry(u):
            return fetch(u)
        """,
    "auth.py": """
        from .errors import AuthError
        from .net import connect, fetch
        def login(u):
            connect(u)
            raise AuthError()
        def token(u):
            return fetch(u)
        def refresh(u):
            return login(u)
        """,
    "api.py": """
        from .net import fetch, connect
        from .auth import login
        def get(u): return fetch(u)
        def post(u): return connect(u)
        def session(u): return login(u)
        """,
}


def t_cli(tmp):
    print("cli")
    src = os.path.join(tmp, "mini")
    os.makedirs(src)
    for f, body in PKG.items():
        open(os.path.join(src, f), "w").write(textwrap.dedent(body))
    out = os.path.join(tmp, "mini_facts")
    r = egm("extract", "python", f"mini={src}", "-o", out)
    facts = open(out + ".txt").read().splitlines()
    check("extract: writes facts and truth", r.returncode == 0 and os.path.exists(out + ".truth.json") and len(facts) > 20, r.stderr)
    check("extract: qualified names, static calls only", "mini__fetch calls mini__connect" in facts and "mini__get calls mini__fetch" in facts)
    check("extract: inheritance and raises", "mini__TimeoutErr inherits from mini__NetError" in facts and "mini__open_socket raises mini__TimeoutErr" in facts)
    kb = os.path.join(tmp, "mini.vtx")
    r = egm("build", out + ".txt", "-o", kb)
    check("build: saves a knowledge base", r.returncode == 0 and os.path.exists(kb), r.stderr)
    r = egm("ask", kb, "? calls mini__connect")
    callers = {l.split("\t")[0].split()[0] for l in r.stdout.splitlines() if l.strip()}
    check("ask: callers of connect", callers == {"mini__fetch", "mini__login", "mini__post"}, r.stdout)
    r = egm("ask", kb, "mini__retry calls ?", "--json")
    j = json.loads(r.stdout)
    check("ask --json: structured results", j["results"] and {"subject", "relation", "object", "status", "tier"} <= set(j["results"][0]), r.stdout)
    r = egm("ask", kb, "mini__get frobnicates ?")
    check("ask: explains an unknown relation instead of returning nothing", "not a learned relation" in r.stderr, r.stderr)
    r = egm("ask", out + ".txt", "? calls mini__connect")
    check("ask: accepts a facts file directly", "mini__post" in r.stdout)
    r = egm("rules", kb)
    check("rules: lists learned relations", "? calls ?" in r.stdout and "? raises ?" in r.stdout, r.stdout)
    # observe: a snapshot replaces what the record said before, and the old value becomes history
    okb = os.path.join(tmp, "obs.vtx")
    egm("build", out + ".txt", "-o", okb)
    egm("observe", okb, "--source", "repo", "--record", "net.py", "--time", "1", "-f", "mini__ping calls mini__connect",
        "-f", "mini__ping calls mini__fetch", "-f", "mini__pong calls mini__fetch")
    egm("observe", okb, "--source", "repo", "--record", "net.py", "--time", "2", "-f", "mini__ping calls mini__fetch",
        "-f", "mini__pong calls mini__fetch")
    r = egm("ask", okb, "mini__ping calls ?", "--json")
    st = {(x["object"], x["status"]) for x in json.loads(r.stdout)["results"]}
    check("observe: snapshot supersedes, old value kept as history",
          ("mini__fetch", "stated") in st and ("mini__connect", "historical") in st and ("mini__connect", "stated") not in st, st)
    # questions are deterministic and the key never reaches the public file
    qd1, qd2 = os.path.join(tmp, "q1"), os.path.join(tmp, "q2")
    tr = out + ".truth.json"
    egm("questions", tr, "-o", qd1, "--seed", "7"); egm("questions", tr, "-o", qd2, "--seed", "7")
    pub = json.load(open(os.path.join(qd1, "questions.json")))
    check("questions: same seed gives the same set",
          open(os.path.join(qd1, "key.json")).read() == open(os.path.join(qd2, "key.json")).read() and len(pub) > 5)
    check("questions: public file has no answers", all("truth" not in q for q in pub))
    ans = os.path.join(tmp, "answers.json")
    r = egm("answer", kb, os.path.join(qd1, "questions.json"), "-o", ans)
    check("answer: scripted solver runs", r.returncode == 0 and len(json.load(open(ans))) == len(pub), r.stderr)
    r = egm("score", os.path.join(qd1, "key.json"), ans, "--expect", "1.0", expect=None)
    check("score: parser-built facts answer their own questions perfectly", r.returncode == 0, r.stdout)
    r = egm("score", os.path.join(qd1, "key.json"), ans, "--expect", "0.5", expect=None)
    check("score --expect: fails on a wrong expectation", r.returncode == 1)
    script = os.path.join(tmp, "cmds.txt")
    open(script, "w").write("# comment\nASK mini__fetch calls ?\nINFER ALL\n")
    r = egm("run", kb, script)
    check("run: raw engine commands", "> ASK mini__fetch calls ?" in r.stdout and "mini__connect" in r.stdout, r.stdout)
    r = egm("bench", out + ".txt", "--queries", "5")
    check("bench: prints timings", "ask p50 ms" in r.stdout, r.stderr)
    # negative control: too few facts means no relation, and egm says why
    few = os.path.join(tmp, "few.txt")
    open(few, "w").write("alice parent of bob\nbob parent of carol\n")
    r = egm("ask", few, "alice parent of ?")
    check("cold start: two facts form no relation, and the message says so", "at least 3 facts" in r.stderr, r.stderr)


# --- repro ----------------------------------------------------------------------------------
def t_repro(tmp):
    print("repro")
    rq = os.path.join(EX, "requests")
    r = egm("eval", os.path.join(rq, "facts_haiku.txt"), os.path.join(rq, "key.json"), "--expect", "0.993", expect=None)
    check("Requests use case: EGM-script on Haiku's facts, mean F1 0.993", r.returncode == 0, r.stdout)
    tk = os.path.join(EX, "tokenomics")
    for size, f1 in (("S", 1.0), ("M", 0.972), ("L", 1.0)):
        r = egm("eval", os.path.join(tk, f"{size}.txt"), os.path.join(tk, "key.json"), "--expect", str(f1), expect=None)
        check(f"tokenomics {size}: EGM-script mean F1 {f1:.3f}", r.returncode == 0, r.stdout)
        r = egm("eval", os.path.join(tk, f"{size}.txt"), os.path.join(tk, "key.json"), "--strict", "--expect", "1.0", expect=None)
        check(f"tokenomics {size}: strict policy mean F1 1.000 (exploratory result)", r.returncode == 0, r.stdout)


def main():
    global EGM
    p = argparse.ArgumentParser(); p.add_argument("--egm", required=True); p.add_argument("--only", default="engine,cli,repro")
    a = p.parse_args()
    EGM = os.path.abspath(a.egm)
    if not os.path.exists(engine_bin()):
        sys.exit(f"engine not built: {engine_bin()} (run make)")
    tmp = tempfile.mkdtemp(prefix="egm_test_")
    try:
        groups = {"engine": t_engine, "cli": t_cli, "repro": t_repro}
        for g in a.only.split(","):
            groups[g](tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
