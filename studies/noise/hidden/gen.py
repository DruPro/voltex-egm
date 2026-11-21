"""Worlds for the noise study. Each function returns (lines, hidden) where lines are all the engine sees and hidden holds
the truth: {"truth": [[rel, a, b], ...], "corrupted": [[rel, a, wrong, right], ...], "relations": [...]}.

  company(seed, scale, noise, reports)   people -> team -> department -> city, reporting lines, collaboration, decoys.
                                         Noise replaces a person's city or team with a wrong one, per report.
  hidden(seed, scale, coverage, noise, reports)   the Blind World (hidden_world.py): laws, exceptions, a conditional
                                         rule, correlation decoys, unseen and sparse people. Noise on its one-value relations.
  gates(seed, per_kind, noise)           xor/and/or/nand gates and a random gate; noise flips stated wire values.
  lineage(seed)                          parent facts; great-grandparent stated for 25 of 40 families (CHAIN 3 world).

reports > 1: every fact of a noisy relation is reported that many times, each report corrupted independently.
"""
import random, collections
import hidden_world

ONE_VALUE_COMPANY = ("is based in", "is on")


def _emit(facts, noisy_rels, pool_of, noise, reports, rng):
    """facts: iterable of (rel, a, b). Returns lines and corruptions. Each report of a noisy fact is wrong with prob noise."""
    lines, corrupted = [], []
    for rel, a, b in facts:
        n = reports if rel in noisy_rels else 1
        for _ in range(n):
            if rel in noisy_rels and rng.random() < noise:
                w = rng.choice([x for x in pool_of(rel, a, b) if x != b]); lines.append(f"{a} {rel} {w}"); corrupted.append([rel, a, w, b])
            else:
                lines.append(f"{a} {rel} {b}")
    return lines, corrupted


def company(seed=0, scale=1.0, noise=0.0, reports=1):
    r = random.Random(1000 + seed)
    syl = ["ka", "lo", "mi", "ne", "ru", "sa", "ti", "vo", "ze", "pa", "do", "fi", "gu", "he", "jo", "be", "ra", "ki"]
    used = set()

    def nm():
        while True:
            s = "".join(r.choice(syl) for _ in range(3)) + r.choice(syl)
            if s not in used: used.add(s); return s
    cities = ["denver", "boston", "austin", "seattle", "miami", "chicago"]
    depts = ["sales", "legal", "finance", "research", "support", "design", "security", "logistics"]
    dept_city = {d: cities[i % 6] for i, d in enumerate(depts)}
    vps = [nm(), nm()]; director = {d: nm() for d in depts}
    teams = [f"team{i:03d}" for i in range(int(40 * scale))]
    team_dept = {t: depts[i % 8] for i, t in enumerate(teams)}
    lead = {t: nm() for t in teams}; members = {t: [nm() for _ in range(10)] for t in teams}
    foods = ["pizza", "sushi", "tacos", "curry", "salad", "ramen", "pasta", "soup", "burgers", "dumplings"]
    T, S = collections.defaultdict(set), collections.defaultdict(set)
    for d in depts: T["is based in"].add((d, dept_city[d])); S["is based in"].add((d, dept_city[d]))
    person_team = {}
    for t in teams:
        T["belongs to"].add((t, team_dept[t])); S["belongs to"].add((t, team_dept[t]))
        c = dept_city[team_dept[t]]; T["is based in"].add((t, c))
        if r.random() < 0.5: S["is based in"].add((t, c))
        for p in members[t] + [lead[t]]:
            person_team[p] = t; T["is on"].add((p, t)); S["is on"].add((p, t)); T["is based in"].add((p, c))
            if r.random() < 0.3: S["is based in"].add((p, c))
    up = {}
    for t in teams:
        for m in members[t]: up[m] = lead[t]
        up[lead[t]] = director[team_dept[t]]
    for i, d in enumerate(depts): up[director[d]] = vps[i % 2]
    for p in up:
        x = p; first = True
        while x in up:
            x = up[x]; T["works under"].add((p, x))
            if first or r.random() < 0.3: S["works under"].add((p, x))
            first = False
    for t in teams:
        for m in members[t]:
            for q in r.sample([x for x in members[t] if x != m], 2):
                T["collaborates with"] |= {(m, q), (q, m)}; S["collaborates with"].add((m, q))
                if r.random() < 0.6: S["collaborates with"].add((q, m))
    everyone = sorted(person_team)
    for p in everyone:
        for q in r.sample(everyone, 2):
            if q != p: T["knows"].add((p, q)); S["knows"].add((p, q))
        f = r.choice(foods); T["likes"].add((p, f)); S["likes"].add((p, f))
    facts = sorted((rel, a, b) for rel, fs in S.items() for a, b in fs)
    nr = random.Random(2000 + seed * 31 + int(noise * 1000) + reports)

    def pool_of(rel, a, b):
        return cities if rel == "is based in" else teams
    noisy = lambda rel, a: rel in ONE_VALUE_COMPANY and a in person_team
    lines, corrupted = [], []
    for rel, a, b in facts:
        l, c = _emit([(rel, a, b)], {rel} if noisy(rel, a) else set(), pool_of, noise, reports, nr); lines += l; corrupted += c
    nr.shuffle(lines)
    return lines, {"truth": sorted([rel, a, b] for rel, fs in T.items() for a, b in fs), "corrupted": corrupted, "relations": sorted(T)}


def hidden(seed=0, scale=1, coverage=0.5, noise=0.03, reports=1, contradict=None):
    """contradict: share of 'lives in' facts given a second, wrong value (default: the Blind World's 1%)."""
    T, ents = hidden_world.generate(seed, scale)
    if reports == 1:
        lines, info = hidden_world.observe(T, ents, seed, coverage, noise=noise, **({} if contradict is None else {"contradict": contradict}))
        corrupted = [[w[0], w[1], w[2], w[4]] for w in info["wrong"]]
        return lines, {"truth": sorted([p, a, b] for p, fs in T.items() for a, b in fs), "corrupted": corrupted,
                       "relations": sorted(T), "unseen": info["unseen"]}
    lines0, info = hidden_world.observe(T, ents, seed, coverage, noise=0.0, contradict=0.0)   # clean sample, then noisy reports
    typ = {e: t for t, es in ents.items() for e in es}
    nr = random.Random(3000 + seed * 31 + int(noise * 1000) + reports)
    facts = [tuple(f) for f in info["observed"]]
    lines, corrupted = _emit(facts, {"lives in", "works as", "is located in"}, lambda rel, a, b: ents[typ[b]], noise, reports, nr)
    nr.shuffle(lines)
    return lines, {"truth": sorted([p, a, b] for p, fs in T.items() for a, b in fs), "corrupted": corrupted,
                   "relations": sorted(T), "unseen": info["unseen"]}


def gates(seed=0, per_kind=200, noise=0.0):
    OPS = {"xor": lambda a, b: a ^ b, "and": lambda a, b: a & b, "or": lambda a, b: a | b, "nand": lambda a, b: 1 - (a & b)}
    W = {0: "zero", 1: "one"}
    r = random.Random(4000 + seed)
    syl = [a + b for a in "bdfgklmnprstvz" for b in "aeiou"]
    pool = [x + y + z for x in syl for y in syl for z in syl[:12]]; r.shuffle(pool); it = iter(pool)
    T, lines, corrupted = [], [], []
    nr = random.Random(5000 + seed * 31 + int(noise * 1000))

    def val(w, v, stated):
        T.append(["has value", w, W[v]])
        if stated:
            if nr.random() < noise: lines.append(f"{w} has value {W[1 - v]}"); corrupted.append(["has value", w, W[1 - v], W[v]])
            else: lines.append(f"{w} has value {W[v]}")
    for kind in ["xor", "and", "or", "nand", "rnd"]:
        for _ in range(per_kind):
            g, w1, w2, w3 = next(it), next(it), next(it), next(it); a, b = r.randint(0, 1), r.randint(0, 1)
            out = r.randint(0, 1) if kind == "rnd" else OPS[kind](a, b)
            for rel, x, y in [("is output of", w3, g), ("has first input", g, w1), ("has second input", g, w2), ("has kind", g, kind)]:
                lines.append(f"{x} {rel} {y}"); T.append([rel, x, y])
            val(w1, a, True); val(w2, b, True); val(w3, out, r.random() < 2 / 3)
    r.shuffle(lines)
    return lines, {"truth": sorted(T), "corrupted": corrupted, "relations": ["has first input", "has kind", "has second input", "has value", "is output of"]}


def lineage(seed=0):
    r = random.Random(6000 + seed)
    syl = ["ka", "mo", "ri", "tu", "se", "ne", "lo", "fa", "di", "ze", "bo", "ja", "vu", "pe", "xi", "go"]
    names = sorted({a + b + c for a in syl for b in syl for c in syl}); r.shuffle(names); it = iter(names)
    lines, T = [], []
    for f in range(40):
        gens = [[next(it)]]
        for g in range(1, 4):
            gens.append([])
            for p in gens[g - 1]:
                for _ in range(2):
                    c = next(it); gens[g].append(c); lines.append(f"{p} is parent of {c}"); T.append(["is parent of", p, c])
        for y in gens[3]:
            T.append(["is great grandparent of", gens[0][0], y])
            if f < 25: lines.append(f"{gens[0][0]} is great grandparent of {y}")
    r.shuffle(lines)
    return lines, {"truth": sorted(T), "corrupted": [], "relations": ["is great grandparent of", "is parent of"]}


WORLDS = {"company": company, "hidden": hidden, "gates": gates, "lineage": lineage}
