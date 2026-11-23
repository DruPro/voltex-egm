"""Real-data confirmation sets for Round 2 (unseen by the round: no engine run on them before the pre-registration
hash). See REALDATA.md for provenance, truth and independence.

  python3 realdata2.py build     writes realdata/<set>/split<seed>/facts.txt and key.txt, and realdata/manifest.json
  load(name, seed) -> World      truth computed here, deterministically, from the sources

Sets (all on this machine; five held-out splits each, seeds 2000-2004; 20% of facts hidden per split):
  c_headers    C headers under /usr/include (studies/stress codebase layer, first 400,000 lines in sorted walk order):
               includes, is declared in, is a, has field of type, returns, aliases. Truth: the extracted facts.
  timezones    /usr/share/zoneinfo zone.tab and iso3166.tab (stress world layer): zone in country, zone in area,
               country name words. Truth: the extracted facts.
  services     /etc/services (stress world layer): uses port, uses protocol, is alias of. Truth: the extracted facts.
  py_requires  installed Python distributions (importlib.metadata): requires (Requires-Dist without an environment
               marker), has extra, provides module (top_level.txt). Truth: the extracted facts.
As in Round 1's dpkg, a derived transitive `includes` or `requires` is not a true fact under this definition.
"""
import hashlib, importlib.metadata, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "realdata")
sys.path[:0] = [os.path.join(ROOT, "studies", "stress", "layers"), os.path.join(ROOT, "studies", "capability", "tools")]
SEEDS = range(2000, 2005)
SETS = ("c_headers", "timezones", "services", "py_requires")
_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _norm(n):
    return "py_" + re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


def py_requires():
    facts = set()
    for d in sorted(importlib.metadata.distributions(), key=lambda x: (x.metadata["Name"] or "").lower()):
        name = d.metadata["Name"]
        if not name:
            continue
        p = _norm(name)
        for r in d.requires or []:
            req, _, marker = r.partition(";")
            m = _NAME.match(req)
            if not m:
                continue
            if "extra" in marker:
                ex = re.search(r"extra\s*==\s*['\"]([^'\"]+)", marker)
                if ex:
                    facts.add(f"{p} has extra x_{re.sub(r'[^a-z0-9]+', '_', ex.group(1).lower())}")
                continue
            if marker.strip():
                continue
            q = _norm(m.group(1))
            if q != p:
                facts.add(f"{p} requires {q}")
        top = d.read_text("top_level.txt") or ""
        for mod in top.split():
            mod = re.sub(r"[^A-Za-z0-9_]", "_", mod).strip("_")
            if mod:
                facts.add(f"{p} provides module m_{mod.lower()}")
    return sorted(facts)


def source(name):
    import codebase, world
    if name == "c_headers":
        return codebase.c_headers("/usr/include", max_lines=400000)[0]
    if name == "timezones":
        return world.timezones()[0]
    if name == "services":
        return world.services()[0]
    return py_requires()


def _relations(facts):
    rels = set()
    for f in facts:
        p = f.split()
        rels.add(" ".join(p[1:-1]))
    return rels


def build():
    man = {"python": sys.version.split()[0], "sources": {}, "sets": {}}
    for f in ("/etc/services", "/usr/share/zoneinfo/zone.tab", "/usr/share/zoneinfo/iso3166.tab"):
        man["sources"][f] = hashlib.sha256(open(f, "rb").read()).hexdigest()
    for name in SETS:
        facts = source(name)
        man["sets"].setdefault(name, {})["facts_total"] = len(facts)
        man["sets"][name]["truth_sha256"] = hashlib.sha256("\n".join(facts).encode()).hexdigest()[:16]
        for seed in SEEDS:
            d = os.path.join(OUT, name, f"split{seed}"); os.makedirs(d, exist_ok=True)
            r = random.Random(seed); stated, key = [], []
            for f in facts:
                (key if r.random() < 0.2 else stated).append(f)
            open(os.path.join(d, "facts.txt"), "w").write("\n".join(stated) + "\n")
            open(os.path.join(d, "key.txt"), "w").write("\n".join(key) + "\n")
            man["sets"][name][str(seed)] = {"stated": len(stated), "hidden": len(key),
                                            "words": len({w for l in stated for w in l.split()}),
                                            "facts_sha256": hashlib.sha256("\n".join(stated).encode()).hexdigest()[:16]}
        print(name, len(facts), "facts", sorted(_relations(facts)), flush=True)
    json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)


_TRUTH = {}


def load(name, seed):
    import cworlds
    from interface import parse_fact
    d = os.path.join(OUT, name, f"split{seed}")
    st = [l for l in open(os.path.join(d, "facts.txt")).read().splitlines() if l.strip()]
    key = [l for l in open(os.path.join(d, "key.txt")).read().splitlines() if l.strip()]
    if name not in _TRUTH:
        _TRUTH[name] = st + key        # the split is a partition of the extracted facts, which are the truth
    facts = _TRUTH[name]
    rels = sorted(_relations(facts), key=len, reverse=True)
    truth = {f for f in (parse_fact(x, rels) for x in facts) if f}
    w = cworlds.World(name, f"real: {name}", seed, st, rels, truth, set(), set(), None, {})
    w.recall_truth = {f for f in (parse_fact(x, rels) for x in key) if f}
    w.maxwords = len({x for l in st for x in l.split()}) + 1000
    return w


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        build()
