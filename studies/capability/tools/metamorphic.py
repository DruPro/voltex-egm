"""C9 consistency: answers must not depend on irrelevant choices. Each transform changes the observations in a way that
should not change any answer, then maps the answers back; the suite compares them with the untransformed run."""
import random

from interface import parse_fact


def _b36(i):
    s = "0123456789abcdefghijklmnopqrstuvwxyz"; o = ""
    while True:
        o = s[i % 36] + o; i //= 36
        if not i:
            return o


def rename(lines, rels, seed):
    """Consistent renaming of every entity (subject and object tokens). Relation phrases are kept."""
    rels = sorted(rels, key=len, reverse=True)
    ents = sorted({x for l in lines for f in [parse_fact(l, rels)] if f for x in (f[1], f[2])})
    r = random.Random(seed); fresh = [f"q{_b36(i)}z" for i in range(len(ents))]; r.shuffle(fresh)
    fwd = dict(zip(ents, fresh)); back = {v: k for k, v in fwd.items()}
    out = []
    for l in lines:
        f = parse_fact(l, rels)
        out.append(f"{fwd[f[1]]} {f[0]} {fwd[f[2]]}" if f else l)
    return out, (lambda f: (f[0], back.get(f[1]), back.get(f[2])))


def shuffle(lines, rels, seed):
    out = list(lines); random.Random(seed).shuffle(out)
    return out, (lambda f: f)


def duplicate(lines, rels, seed):
    return [l for l in lines for _ in (0, 1)], (lambda f: f)


DISTRACT_RELS = ["zaps toward", "hums beside"]


def distract(lines, rels, seed):
    """Add an unrelated random graph (new entities, new relation phrases) half the size of the world."""
    r = random.Random(seed); names = [f"dz{_b36(i)}x" for i in range(200)]
    extra = [f"{a} {r.choice(DISTRACT_RELS)} {b}" for _ in range(max(50, len(lines) // 2)) for a, b in [r.sample(names, 2)]]
    out = list(lines) + extra; r.shuffle(out)
    return out, (lambda f: None if f[0] in DISTRACT_RELS or str(f[1]).startswith("dz") or str(f[2]).startswith("dz") else f)


TRANSFORMS = {"rename": rename, "shuffle": shuffle, "duplicate": duplicate, "distract": distract}


def compare(base, other):
    """Jaccard similarity of two sets of derived facts (1.0 = identical; both empty = 1.0, identical by definition)."""
    if not base and not other:
        return 1.0
    return len(base & other) / len(base | other)
