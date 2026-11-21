"""egm.shard (EXPERIMENTAL): several unchanged engines, one answer set. See docs/SDK.md.

Use it for independent sources: fact sets that don't describe the same entities and shouldn't share rules
(separate codebases, customers, domains).

    import egm
    r = egm.shard({"billing": "billing.txt", "search": search_lines}, jobs=2)
    r.facts        # [Fact(...)], derived facts with tier and source (the source(s) that derived each)
    r.warnings     # sources sharing entities (then they aren't independent), empty sources, capacity limits
    r.report       # per source: facts, derived, seconds

One engine per source; nothing is routed between sources; consensus is off unless asked for.

It is not the way to handle large data: one engine (CLUSTERSTREAM, on by default) handled 244,444 facts in 256 MB with exact
answers (studies/scaling).

Splitting one fact set (``shards`` with ``graph`` or ``key``) is kept as an experimental option. It reproduces one
engine only if the split keeps each fact's evidence together and leaves every shard a fair sample of every rule. A
user-named clean split did that on the company world (studies/shard). A split derived from the data did it on 2 of
6 world shapes (studies/shard_general). Every engine gets MAXWORDS sized to its own input unless settings sets it.
"""
import collections
import collections.abc
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Union

from . import parse
from .engine import find_binary
from .errors import EngineError
from .model import Fact, _Dict

_COMMANDS = ["RELATIONS", "INFER ALL", "CONFLICTS"]


@dataclass
class ShardResult(_Dict):
    """The union of the shards' answers.

    facts     derived facts (status "inferred"), each with the strongest tier any engine gave it
    warnings  what the split could not do (each also counted in report)
    report    shards, assigned entities, reference facts, per-engine facts/seconds/limits, consensus drops
    """
    facts: List[Fact]
    warnings: List[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)


def _split(line):
    w = line.split()
    if len(w) < 3:
        return None
    return w[0], " ".join(w[1:-1]), w[-1]


def _maxwords_for(lines):
    return max(12000, len({x for l in lines for x in l.split()}) + 1000)


def _run(binary, path, settings, extra=()):
    cmds = "\n".join([f"SET {k} {v}" for k, v in settings.items()] + [f"INGESTFILE {path}"] + _COMMANDS + list(extra) + ["EXIT"]) + "\n"
    t = time.time()
    p = subprocess.run([binary], input=cmds, capture_output=True, text=True)
    if p.returncode != 0:
        raise EngineError(f"engine exited with status {p.returncode} on {os.path.basename(path)}")
    return p.stdout, round(time.time() - t, 3)


def _facts_out(out):
    r = []
    for l in out.splitlines():
        if l.startswith("FACT\t"):
            p = l.split("\t"); r.append((p[1], p[2] if len(p) > 2 else ""))
    return r


def _accepted_rules(out):
    return {l.strip()[len("ACCEPT "):].split(" n=")[0].strip() for l in out.splitlines() if l.strip().startswith("ACCEPT ")}


def _proofs(out):
    r = {}
    for l in out.splitlines():
        if " inferred" not in l or " because " not in l or "[rule: " not in l or l.startswith("FACT"):
            continue
        head = l.strip().split(" inferred")[0].strip()
        body, rule = l.split(" because ", 1)[1].split("  [rule: ", 1)
        r[" ".join(head.split())] = (rule.rsplit("]", 1)[0].strip(), [" ".join(x.split()) for x in body.split(" + ")])
    return r


def _asks_for(facts):
    return sorted({f"ASK {f[0]} {f[1]} ?" for f in map(_split, facts) if f})


def _assign(lines, n, graph, attach, key):
    parsed = [_split(l) for l in lines]
    shard_of = {}
    if key is not None:
        objs = sorted({f[2] for f in parsed if f and f[1] == key})
        home = {o: i % n for i, o in enumerate(objs)}
        votes = collections.defaultdict(collections.Counter)
        for f in parsed:
            if f and f[1] == key:
                votes[f[0]][f[2]] += 1
        for s, c in votes.items():
            shard_of[s] = home[sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]]
        return shard_of
    adj = collections.defaultdict(set)
    for f in parsed:
        if f and f[1] in graph:
            adj[f[0]].add(f[2]); adj[f[2]].add(f[0])
    seen, comps = set(), []
    for v in sorted(adj):
        if v in seen:
            continue
        comp, stack = [], [v]; seen.add(v)
        while stack:
            x = stack.pop(); comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y); stack.append(y)
        comps.append(sorted(comp))
    comps.sort(key=lambda c: (-len(c), c[0]))
    load = [0] * n
    for c in comps:
        i = min(range(n), key=lambda j: (load[j], j)); load[i] += len(c)
        for x in c:
            shard_of[x] = i
    nb = collections.defaultdict(set)
    for f in parsed:
        if f and f[1] in attach:
            nb[f[0]].add(f[2]); nb[f[2]].add(f[0])
    add = {}
    for v in sorted(nb):
        if v in shard_of:
            continue
        homes = {shard_of[y] for y in nb[v] if y in shard_of}
        if len(homes) == 1:
            add[v] = homes.pop()
    shard_of.update(add)                      # one pass: attached entities do not attach others
    return shard_of


def _route(lines, n, shard_of, extra_reference=()):
    own = [[] for _ in range(n)]
    ref_idx = []
    for i, l in enumerate(lines):
        f = _split(l)
        if not f:
            continue
        s = shard_of.get(f[0], shard_of.get(f[2]))
        if s is None:
            ref_idx.append(i)
        else:
            own[s].append(i)
    ref_lines = [lines[i] for i in ref_idx] + list(extra_reference)
    by_subject = collections.defaultdict(list)
    for j, l in enumerate(ref_lines):
        by_subject[_split(l)[0]].append(j)
    shards = []
    for s in range(n):
        mentioned = set()
        for i in own[s]:
            f = _split(lines[i]); mentioned.add(f[0]); mentioned.add(f[2])
        taken, frontier = set(), list(mentioned)
        while frontier:
            e = frontier.pop()
            for j in by_subject.get(e, ()):
                if j in taken:
                    continue
                taken.add(j); o = _split(ref_lines[j])[2]
                if o not in mentioned:
                    mentioned.add(o); frontier.append(o)
        pos = set(own[s]) | {ref_idx[j] for j in taken if j < len(ref_idx)}
        shards.append([lines[i] for i in sorted(pos)] + [ref_lines[j] for j in sorted(taken) if j >= len(ref_idx)])
    return shards, ref_lines


def shard(facts: Union[str, Iterable[str], Mapping[str, Union[str, Iterable[str]]]], shards: Optional[int] = None,
          graph: Optional[Sequence[str]] = None, attach: Sequence[str] = (), key: Optional[str] = None,
          central: bool = False, consensus: Optional[bool] = None, settings: Optional[Dict] = None,
          binary: Optional[str] = None, jobs: int = 1, workdir: Optional[str] = None) -> ShardResult:
    """Run several engines and return the union of their answers.

    Independent sources (recommended): ``facts={"name": file_or_lines, ...}``. One engine per source, nothing is
    routed between them, each answer's ``source`` names the source(s) that derived it, and ``consensus`` defaults to
    False (sources may follow different rules). ``shards``, ``graph``, ``attach``, ``key`` and ``central`` must be
    left out.

    Splitting one fact set (experimental; see docs/SDK.md): ``facts`` is a file or lines, ``shards`` is required, and
    exactly one of ``graph`` or ``key`` says how to split. ``consensus`` defaults to True.

    Args:
        facts: a mapping {source name: facts file or lines}, or one facts file (one ``subject relation words object``
            per line, one-word names), or an iterable of lines.
        shards: number of engines when splitting (the split may leave some empty; they are skipped and reported).
        graph: relation phrases (e.g. ``["collaborates with"]``) whose connected components define the shards. Choose
            relations your noise can't corrupt.
        attach: relation phrases that place an unassigned entity in the one shard all its assigned neighbours share
            (e.g. a team lead through ``works under``).
        key: instead of ``graph``, split each subject of this relation by its object (the scale study's split; it
            loses precision when the key relation is noisy).
        central: learn rules about reference facts once, centrally, and pass the law-tier conclusions to the shards.
        consensus: keep only answers whose rule more than half the engines accepted. Default: False for sources,
            True when splitting.
        settings: engine settings for every engine, e.g. ``{"TENDENCYSTEPS": 0}``. ``MAXWORDS`` is sized per engine
            unless given here.
        binary: path to voltex2 (otherwise found as for ``egm.Engine``).
        jobs: engines run at the same time (default 1). The answers don't depend on it.
        workdir: keep the shard files and engine outputs here (default: a temporary directory, removed afterwards).
    """
    if isinstance(facts, collections.abc.Mapping):
        if graph is not None or key is not None or attach or central:
            raise ValueError("with sources, leave out graph, attach, key and central: nothing is routed between sources")
        if shards is not None and shards != len(facts):
            raise ValueError("with sources there is one engine per source; leave out shards")
        if not facts:
            raise ValueError("no sources given")
        sources = {str(k): _lines_of(v) for k, v in facts.items()}
        return _in_workdir(workdir, lambda wd: _sources(sources, bool(consensus), dict(settings or {}), find_binary(binary),
                                                         max(1, jobs), wd))
    if (graph is None) == (key is None):
        raise ValueError("give exactly one of graph=[relations] or key=relation (or pass facts as {source: facts})")
    if shards is None or shards < 1:
        raise ValueError("shards must be at least 1 when splitting one fact set")
    consensus = True if consensus is None else consensus
    binary = find_binary(binary)
    settings = dict(settings or {})
    if isinstance(facts, str):
        if not os.path.isfile(facts):
            raise FileNotFoundError(facts)
        with open(facts) as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
    else:
        lines = [l.strip() for l in facts if l.strip()]
    tmp = None
    if workdir is None:
        tmp = tempfile.TemporaryDirectory(prefix="egm_shard_"); workdir = tmp.name
    os.makedirs(workdir, exist_ok=True)
    try:
        return _shard(lines, shards, set(graph or ()), set(attach), key, central, consensus, settings, binary, max(1, jobs), workdir)
    finally:
        if tmp is not None:
            tmp.cleanup()


def _lines_of(facts):
    if isinstance(facts, str):
        if not os.path.isfile(facts):
            raise FileNotFoundError(facts)
        with open(facts) as fh:
            return [l for l in fh.read().splitlines() if l.strip()]
    return [l.strip() for l in facts if l.strip()]


def _in_workdir(workdir, fn):
    tmp = None
    if workdir is None:
        tmp = tempfile.TemporaryDirectory(prefix="egm_shard_"); workdir = tmp.name
    os.makedirs(workdir, exist_ok=True)
    try:
        return fn(workdir)
    finally:
        if tmp is not None:
            tmp.cleanup()


def _sources(sources, consensus, settings, binary, jobs, workdir):
    """One engine per independent source; union of answers, each tagged with the source(s) that derived it."""
    warnings = []
    names = sorted(sources)
    files = {}

    def write(name, ls):
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
        p = os.path.join(workdir, f"src{len(files):03d}_{safe}.txt"); files[name] = p
        with open(p, "w") as fh:
            fh.write("\n".join(ls) + "\n")
        return p
    empty = [n for n in names if not sources[n]]
    if empty:
        warnings.append(f"{len(empty)} source(s) have no facts and were skipped: {', '.join(empty[:5])}")
    live = [n for n in names if sources[n]]
    owners = collections.defaultdict(set)
    for n in live:
        for l in sources[n]:
            f = _split(l)
            if f:
                owners[f[0]].add(n); owners[f[2]].add(n)
    shared = sorted(e for e, o in owners.items() if len(o) > 1)
    if shared:
        warnings.append(f"{len(shared)} entities appear in more than one source (first: {shared[0]!r}); each source "
                        f"answers about them from its own facts only. If the sources describe the same entities, "
                        f"they are not independent: one engine over all of them is the exact answer.")
    results = _run_parts([(n, sources[n]) for n in live], consensus, settings, binary, jobs, write)
    report = {"mode": "sources", "consensus": consensus, "sources": {}, "shared_entities": len(shared)}
    for _i, name, size, out, fo, _acc, _pr, sec in results:
        lim = [l for l in out.splitlines() if l.startswith("[LIMIT]")]
        warnings += [f"{name}: {l}" for l in lim]
        report["sources"][name] = {"facts": size, "derived": len(fo), "seconds": sec}
    answers = {}
    kept_by, dropped, minority = _union(results, consensus, answers, len(live))
    if consensus:
        report.update(consensus_dropped=dropped, minority_rules=minority)
    report["seconds"] = round(sum(v["seconds"] for v in report["sources"].values()), 3)
    facts = parse.infer_all([f"FACT\t{f}\t{t}" for f, t in sorted(answers.items())])
    for x in facts:
        x.source = ",".join(sorted(kept_by.get(x.fact, ())))
    return ShardResult(facts=facts, warnings=warnings, report=report)


def _settings_for(lines, settings):
    return {"MAXWORDS": _maxwords_for(lines), **settings} if "MAXWORDS" not in {k.upper() for k in settings} else dict(settings)


def _shard(lines, n, graph, attach, key, central, consensus, settings, binary, jobs, workdir):
    shard_of = _assign(lines, n, graph, attach, key)
    report = {"shards": n, "boundary": "key" if key is not None else "components", "central": central,
              "consensus": consensus, "assigned_entities": len(shard_of), "engines": []}
    warnings, answers, extra = [], {}, []

    def write(name, ls):
        p = os.path.join(workdir, name + ".txt")
        with open(p, "w") as fh:
            fh.write("\n".join(ls) + "\n")
        return p

    def note_limits(name, out):
        for l in out.splitlines():
            if l.startswith("[LIMIT]"):
                warnings.append(f"{name}: {l}")

    if central:
        _, ref = _route(lines, n, shard_of)
        p = write("central", ref)
        out, sec = _run(binary, p, _settings_for(ref, settings))
        note_limits("central", out)
        fo = _facts_out(out)
        extra = [f for f, t in fo if t == "law"]
        for f, t in fo:
            answers.setdefault(f, t)
        report["engines"].append({"name": "central", "facts": len(ref), "law_passed": len(extra), "seconds": sec})
    parts, ref = _route(lines, n, shard_of, extra)
    covered = set()
    for sl in parts:
        covered.update(sl)
    seen_central = set(ref) if central else set()
    unseen = [l for l in lines if l not in covered and l not in seen_central]
    report["reference_facts"] = len(ref) - len(extra)
    report["unseen_facts"] = len(unseen)
    if unseen:
        warnings.append(f"{len(unseen)} facts reached no shard (no shard mentions their subject); "
                        f"first: {unseen[0]!r}. central=True would at least learn from them.")
    live = [s for s, sl in enumerate(parts) if sl]
    if len(live) < n:
        warnings.append(f"{n - len(live)} of {n} shards received no facts (fewer components than shards); they were skipped")

    results = _run_parts([(f"shard{s:02d}", parts[s]) for s in live], consensus, settings, binary, jobs, write)
    for _i, name, size, out, fo, acc, pr, sec in results:
        note_limits(name, out)
        report["engines"].append({"name": name, "facts": size, "derived": len(fo), "seconds": sec})
    _kept, dropped, minority = _union(results, consensus, answers, len(live))
    if consensus:
        report.update(consensus_dropped=dropped, minority_rules=minority)
    report["seconds"] = round(sum(e["seconds"] for e in report["engines"]), 3)
    lines_out = [f"FACT\t{f}\t{t}" for f, t in sorted(answers.items())]
    return ShardResult(facts=parse.infer_all(lines_out), warnings=warnings, report=report)


def _run_parts(parts, consensus, settings, binary, jobs, write):
    """parts: [(name, lines)], all non-empty. One engine each (two sessions with consensus, for the proofs)."""
    def work(i):
        name, sl = parts[i]
        p = write(name, sl); st = _settings_for(sl, settings)
        out, sec = _run(binary, p, st)
        fo = _facts_out(out)
        acc, pr = set(), {}
        if consensus:
            out2, sec2 = _run(binary, p, st, extra=_asks_for(f for f, _ in fo)); sec = round(sec + sec2, 3)
            acc, pr = _accepted_rules(out), _proofs(out2)
        return i, name, len(sl), out, fo, acc, pr, sec
    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            return sorted(ex.map(work, range(len(parts))))
    return [work(i) for i in range(len(parts))]


def _union(results, consensus, answers, live):
    """Merge engine answers into `answers` {fact: tier} (law wins over tendency). With consensus, keep an answer only if
    the rule in its proof was accepted by more than half of the `live` engines and its derived premises are kept.
    Returns ({fact: set of engine names that kept it}, answers dropped, rules accepted by a minority)."""
    kept_by = collections.defaultdict(set)
    if not consensus:
        for _i, name, _n, _out, fo, _acc, _pr, _sec in results:
            for f, t in fo:
                kept_by[f].add(name)
                if answers.get(f) != "law":
                    answers[f] = t
        return kept_by, 0, []
    votes = collections.Counter(r for *_, acc, _pr, _sec in results for r in acc)
    majority = {r for r, c in votes.items() if c > live / 2}
    dropped = 0
    for _i, name, _n, _out, fo, acc, pr, _sec in results:
        derived = {f for f, _ in fo}; memo = {}

        def keep(f, depth=0):
            if f in memo:
                return memo[f]
            memo[f] = False                      # cycle guard
            if f not in pr or depth > 50:
                return False
            rule, prem = pr[f]
            memo[f] = rule in majority and all(keep(x, depth + 1) for x in prem if x in derived)
            return memo[f]
        for f, t in fo:
            if keep(f):
                kept_by[f].add(name)
                if answers.get(f) != "law":
                    answers[f] = t
            else:
                dropped += 1
    return kept_by, dropped, sorted(r for r in votes if r not in majority)
