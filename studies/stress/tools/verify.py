"""Exploratory: score derived facts against ground truth wider than the held-out key.

  unicode   every derived fact is checked against Python's unicodedata (true / false / not checkable)
  packages  a derived "A depends on C" counts as true when C is in A's full transitive Depends/Pre-Depends closure
            (computed from the whole dpkg status, held-out facts included)
Writes ../explore/verify_<name>.json.
"""
import collections, json, os, re, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(STUDY, "layers"))
import egm  # noqa: E402
OBS = os.path.join(STUDY, "obs"); BIN = os.path.join(ROOT, "build", "voltex2")


def ch(t): return chr(int(t[1:], 16))


def uni_truth(f):
    s, rel, o = re.match(r"^(\S+) (.+) (\S+)$", f).groups()
    c = ch(s); name = unicodedata.name(c, None)
    if rel == "has category": return o == "cat_" + unicodedata.category(c)
    if rel == "has bidi class": return o == "bidi_" + unicodedata.bidirectional(c)
    if rel == "is in script": return None if not name else o == "script_" + name.split(" ")[0]
    if rel == "has uppercase": return c.upper() == ch(o)
    if rel == "has lowercase": return c.lower() == ch(o)
    if rel == "decomposes to": d = unicodedata.decomposition(c); return bool(d) and not d.startswith("<") and int(d.split()[0], 16) == int(o[1:], 16)
    if rel == "has combining class": return o == f"ccc_{unicodedata.combining(c)}"
    return None


def closure_truth():
    import world
    deps = collections.defaultdict(set)
    for f in world.packages()[0]:
        m = re.match(r"^(\S+) depends on (\S+)$", f)
        if m: deps[m.group(1)].add(m.group(2))
    memo = {}
    def clo(a):
        if a in memo: return memo[a]
        seen, st = set(), [a]
        while st:
            x = st.pop()
            for y in deps.get(x, ()):
                if y not in seen: seen.add(y); st.append(y)
        memo[a] = seen; return seen
    return clo


def run(name, settings):
    stated = {" ".join(l.split()) for l in open(os.path.join(OBS, name + ".txt")) if l.strip()}
    with egm.open(os.path.join(OBS, name + ".txt"), settings=settings, binary=BIN) as e:
        facts = [f for f in e.infer_all() if " ".join(f.fact.split()) not in stated]
    tally = collections.Counter(); per_rel = collections.defaultdict(collections.Counter)
    out_of_range = collections.Counter()
    clo = closure_truth() if name == "world_packages" else None
    for f in facts:
        t = f.fact
        if name == "world_unicode":
            v = uni_truth(t); s = t.split()[0]
            if not (0x20 <= int(s[1:], 16) < 0x3000): out_of_range["true" if v else "false" if v is False else "unchecked"] += 1
        else:
            m = re.match(r"^(\S+) depends on (\S+)$", t)
            v = (m.group(2) in clo(m.group(1))) if m else None
        k = "true" if v else "false" if v is False else "unchecked"
        tally[k] += 1; per_rel[f.relation][k] += 1
    r = {"dataset": name, "settings": settings, "derived_new": len(facts), "tally": tally, "per_relation": per_rel,
         "subject_outside_extracted_range": out_of_range}
    json.dump(r, open(os.path.join(STUDY, "explore", f"verify_{name}" + ("_" + "_".join(f"{k}{v}" for k, v in settings.items()) if settings else "") + ".json"), "w"), indent=1)
    print(json.dumps(r, indent=1))


if __name__ == "__main__":
    run("world_unicode", {})
    run("world_packages", {"DEPTH": 1}); run("world_packages", {"DEPTH": 2}); run("world_packages", {})
