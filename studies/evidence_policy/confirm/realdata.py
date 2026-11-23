"""Real-data replication sets for Round 1 confirmation. See REALDATA.md for provenance, truth and independence.

  python3 realdata.py build      writes realdata/<set>/split<seed>/facts.txt and key.txt, and realdata/manifest.json
  load(name, seed) -> World      (used by confirm.py; truth is computed here, deterministically, from the sources)

Sets (all on this machine; five held-out splits each, seeds 1000-1004):
  py_stdlib   CPython standard library (/usr/lib/python3.13), facts from Python's own ast (studies/strengths, round 2
              fact design). Truth: every base and target fact, complete. Hidden: 30% of the target facts per split.
  py_dist     the installed dist-packages (/usr/lib/python3/dist-packages): same extractor, independent code.
  unicode     Unicode characters U+0020-U+2FFF (studies/stress world layer). Truth: the same relations computed from
              Python's unicodedata for every named character (so a true fact about a character outside the extracted
              range is true). Hidden: 20% of the facts per split.
  dpkg        installed Debian packages (/var/lib/dpkg/status, studies/stress world layer). Truth: the database's own
              direct facts. Hidden: 20% per split. A derived transitive dependency is NOT a true "depends on" fact under
              this definition; the transitive-closure view is reported separately and counts for no criterion.
"""
import collections, hashlib, json, os, random, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "realdata")
sys.path.insert(0, os.path.join(ROOT, "studies", "strengths", "tools")); sys.path.insert(0, os.path.join(ROOT, "studies", "stress", "layers"))
sys.path.insert(0, os.path.join(ROOT, "studies", "capability", "tools"))
SEEDS = range(1000, 1005)
SETS = ("py_stdlib", "py_dist", "unicode", "dpkg")
PY_ROOTS = {"py_stdlib": "/usr/lib/python3.13", "py_dist": "/usr/lib/python3/dist-packages"}


def _relations(facts):
    return sorted({f.split(" ", 1)[1].rsplit(" ", 1)[0] for f in facts})


def _python(name, seed):
    """strengths' extractor (round 2 design), with the hiding seed replaced by the split seed."""
    import extract
    real = random.Random
    extract.random.Random = lambda s=None: real(seed)        # the extractor hides with Random(11); use the split seed
    d = os.path.join(OUT, name, f"split{seed}")
    os.environ["OBS_DIR"] = d                                  # absolute: os.path.join keeps it as is
    try:
        extract.main(PY_ROOTS[name], r2=True)
    finally:
        extract.random.Random = real; del os.environ["OBS_DIR"]
    t = json.load(open(os.path.join(d, "truth.json")))
    return t["base"] + t["targets"]


def _unicode_truth():
    import world
    return world.unicode(0x0, 0x30000)[0]


def build():
    import world
    man = {"python": sys.version.split()[0], "unicodedata": unicodedata.unidata_version,
           "dpkg_status_sha256": hashlib.sha256(open("/var/lib/dpkg/status", "rb").read()).hexdigest(), "sets": {}}
    for name in SETS:
        for seed in SEEDS:
            d = os.path.join(OUT, name, f"split{seed}"); os.makedirs(d, exist_ok=True)
            if name in PY_ROOTS:
                truth = _python(name, seed)
                # the extractor wrote facts.txt (stated) and key.txt (hidden targets) into d
            else:
                facts = world.unicode()[0] if name == "unicode" else world.packages()[0]
                r = random.Random(seed); stated, key = [], []
                for f in facts:
                    (key if r.random() < 0.2 else stated).append(f)
                open(os.path.join(d, "facts.txt"), "w").write("\n".join(stated) + "\n")
                open(os.path.join(d, "key.txt"), "w").write("\n".join(key) + "\n")
            st = [l for l in open(os.path.join(d, "facts.txt")).read().splitlines() if l.strip()]
            key = [l for l in open(os.path.join(d, "key.txt")).read().splitlines() if l.strip()]
            words = {w for l in st for w in l.split()}
            man["sets"].setdefault(name, {})[str(seed)] = {"stated": len(st), "hidden": len(key), "words": len(words),
                                                            "facts_sha256": hashlib.sha256("\n".join(st).encode()).hexdigest()[:16]}
            print(name, seed, len(st), "stated", len(key), "hidden", len(words), "words", flush=True)
    json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)


_TRUTH = {}


def load(name, seed):
    """A World (cworlds.World) for one split: observations, complete truth, the hidden key as the recall truth."""
    import cworlds
    from interface import parse_fact
    d = os.path.join(OUT, name, f"split{seed}")
    st = [l for l in open(os.path.join(d, "facts.txt")).read().splitlines() if l.strip()]
    key = [l for l in open(os.path.join(d, "key.txt")).read().splitlines() if l.strip()]
    if name not in _TRUTH:
        if name in PY_ROOTS:
            t = json.load(open(os.path.join(d, "truth.json"))); _TRUTH[name] = t["base"] + t["targets"]
        elif name == "unicode":
            _TRUTH[name] = _unicode_truth()
        else:
            import world
            _TRUTH[name] = world.packages()[0]
    facts = _TRUTH[name]
    rels = sorted(_relations(st + key + facts), key=len, reverse=True)
    truth = {f for f in (parse_fact(x, rels) for x in facts) if f}
    w = cworlds.World(name, f"real: {name}", seed, st, rels, truth, set(), set(), None, {})
    w.recall_truth = {f for f in (parse_fact(x, rels) for x in key) if f}
    w.maxwords = len({x for l in st for x in l.split()}) + 1000       # docs/CHOOSING_SETTINGS.md step 1, every profile
    return w


def dpkg_transitive(world, derived):
    """Secondary view, no criterion: derived 'depends on' facts that are in the transitive Depends closure."""
    dep = collections.defaultdict(set)
    for r, a, b in world.truth:
        if r == "depends on":
            dep[a].add(b)

    def clo(a):
        seen, stack = set(), [a]
        while stack:
            for b in dep.get(stack.pop(), ()):
                if b not in seen:
                    seen.add(b); stack.append(b)
        return seen
    cache = {}
    ok = 0; n = 0
    for r, a, b in derived:
        if r != "depends on":
            continue
        n += 1
        if a not in cache:
            cache[a] = clo(a)
        ok += b in cache[a]
    return {"derived_depends": n, "in_transitive_closure": ok}


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build()
