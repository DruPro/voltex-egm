"""Temporary layer: synthetic shapes the existing worlds don't cover (studies/stress). Each returns (lines, key),
key = facts that hold in the world but were not stated (the hidden answer key; never given to the engine).

  zipf(seed, n)            power-law link graph, hub-heavy objects; "links to" plus an attribute that copies along links
  chain(seed, n, length)   long precedence chains, "comes before" stated for part of the chain (deep closures)
  many_rel(seed, n, k)     k unrelated relations, few facts each (relation caps, many small categories)
  clusters(seed, n, c)     c disjoint vocabularies, each with its own relation and values (many class components)
  phrases(seed, n)         multi-word names and values ("north river valley"), stresses the grammar layer
  messy(seed, n)           duplicates, case changes, accented and odd tokens, blank lines
  social(seed, n)          symmetric and inverse relations (married to; employs / works for)
"""
import random

SYL = [a + b for a in "bdfgklmnprstvz" for b in "aeiou"]


def names(r, n, pre=""):
    seen, out = set(), []
    while len(out) < n:
        w = pre + "".join(r.choice(SYL) for _ in range(3)) + str(r.randrange(10))
        if w not in seen: seen.add(w); out.append(w)
    return out


def zipf(seed=0, n=4000):
    r = random.Random(seed); V = names(r, n, "z"); colors = ["red", "blue", "green", "amber", "violet"]
    lines, key = [], []
    color = {v: r.choice(colors) for v in V}
    w = [1.0 / (i + 1) for i in range(n)]
    for v in V:
        for t in r.choices(V, weights=w, k=3):
            if t != v: lines.append(f"{v} links to {t}")
    for v in V:
        (lines if r.random() < 0.7 else key).append(f"{v} has color {color[v]}")
    r.shuffle(lines); return lines, key


def chain(seed=0, n=40, length=30):
    r = random.Random(seed); lines, key = [], []
    for c in range(n):
        xs = names(r, length, f"c{c}x")
        for a, b in zip(xs, xs[1:]): lines.append(f"{a} precedes {b}")
        for i in range(length):
            for j in range(i + 1, min(length, i + 4)):
                (lines if c % 3 else key).append(f"{xs[i]} comes before {xs[j]}")
    r.shuffle(lines); return lines, key


def many_rel(seed=0, n=3000, k=60):
    r = random.Random(seed); E = names(r, n, "m"); rels = [f"rel{i} with" for i in range(k)]
    lines = [f"{r.choice(E)} {r.choice(rels)} {r.choice(E)}" for _ in range(n * 3)]
    return lines, []


def clusters(seed=0, n=6000, c=60):
    r = random.Random(seed); lines, key = [], []
    for g in range(c):
        E = names(r, n // c, f"g{g}e"); vals = [f"g{g}v{i}" for i in range(4)]
        verb = f"g{g}has"
        for e in E:
            v = r.choice(vals); lines.append(f"{e} {verb} {v}")
            friend = r.choice(E)
            if friend != e: lines.append(f"{e} g{g}knows {friend}")
    r.shuffle(lines); return lines, key


def phrases(seed=0, n=3000):
    r = random.Random(seed)
    adj = ["north", "south", "old", "new", "upper", "lower", "east", "west"]
    noun = ["river", "mill", "hill", "valley", "bridge", "market", "harbor", "forest", "gate", "tower"]
    regions = [f"{a} {b} {c}" for a in adj for b in noun for c in ("district", "county", "province")]
    places = [f"the {a} {b}" for a in adj for b in noun]
    lines, key = [], []
    for i in range(n):
        p = f"{r.choice(places)} {i}"; reg = r.choice(regions)
        lines.append(f"{p} is located in {reg}")
        (lines if r.random() < 0.7 else key).append(f"{p} is governed from {reg.split(' ')[0]} capital")
    r.shuffle(lines); return lines, key


def messy(seed=0, n=3000):
    r = random.Random(seed); E = names(r, n, "q"); acc = ["café", "naïve", "smörgås", "über", "jalapeño", "x-ray", "o'neil"]
    lines = []
    for e in E:
        t = r.choice(acc); lines.append(f"{e} likes {t}")
        if r.random() < 0.3: lines.append(f"{e} likes {t}")              # duplicate
        if r.random() < 0.1: lines.append(f"{e.upper()} likes {t}")      # case variant
        if r.random() < 0.05: lines.append("")
        if r.random() < 0.05: lines.append(f"  {e}   likes   {t}  ")    # extra spaces
    return lines, []


def social(seed=0, n=3000):
    r = random.Random(seed); P = names(r, n, "p"); C = names(r, n // 30, "co")
    lines, key = [], []
    r.shuffle(P)
    for a, b in zip(P[0::2], P[1::2]):
        lines.append(f"{a} is married to {b}")
        (lines if r.random() < 0.6 else key).append(f"{b} is married to {a}")
    for p in P:
        c = r.choice(C); lines.append(f"{c} employs {p}")
        (lines if r.random() < 0.6 else key).append(f"{p} works for {c}")
    r.shuffle(lines); return lines, key


SHAPES = {"zipf": zipf, "chain": chain, "many_rel": many_rel, "clusters": clusters, "phrases": phrases,
          "messy": messy, "social": social}
