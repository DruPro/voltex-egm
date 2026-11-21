"""HIDDEN world generator. Voltex never reads anything in hidden/.

Entities (scale=1): 500 individuals, 40 settlements, 12 regions, 8 professions, 6 resources, 4 institutions.
18 predicates. Ground-truth structure:
  laws          lives in + is located in -> is from          (composition, functional)
                is located in <-> contains, is parent of <-> is child of   (inverses)
                borders, is sibling of                        (symmetric)
                is ancestor of = transitive closure of is parent of
                is child of + is parent of -> is sibling of    (siblings share both parents)
                contains + produces -> exports                 (region exports what its settlements produce)
  with exceptions  works as + is overseen by -> is member of   (6% never join, 3% join a second institution)
  conditional   harvests: ONLY farmers and miners harvest what their settlement produces
  non-transitive  borders, knows, trades with, mentors
  correlation decoys (statistically convincing, not laws):
                children usually (80%) live where a parent lives
                trading partners are usually (85%) from the same region
                a mentor usually (90%) shares the mentee's profession
"""
import random, json, collections, itertools

SYL = ["ka", "lo", "mi", "ne", "ru", "sa", "ti", "vo", "ze", "pa", "do", "fi", "gu", "he", "jo", "be", "ra", "ki", "mo", "nu"]
PROFESSIONS = ["farmer", "smith", "healer", "scribe", "merchant", "miner", "weaver", "guard"]
RESOURCES = ["grain", "iron", "herbs", "wool", "salt", "timber"]

# Rules that are TRUE in this world and expressible in Voltex's rule language (inverse / symmetric / 2-step composition).
EXPRESSIBLE_TRUE_RULES = [
    ("C", "lives in", "is located in", "is from"),
    ("I", "is located in", None, "contains"), ("I", "contains", None, "is located in"),
    ("I", "is parent of", None, "is child of"), ("I", "is child of", None, "is parent of"),
    ("I", "is sibling of", None, "is sibling of"), ("I", "borders", None, "borders"),
    ("T", "is ancestor of", "is ancestor of", "is ancestor of"),
    ("C", "is parent of", "is ancestor of", "is ancestor of"), ("C", "is ancestor of", "is parent of", "is ancestor of"),
    ("C", "is child of", "is parent of", "is sibling of"),
    ("C", "contains", "produces", "exports"),
    ("C", "works as", "is overseen by", "is member of"),
]
# True rules Voltex cannot express: single-premise implication, constant-conditioned rule.
INEXPRESSIBLE_TRUE_RULES = ["is parent of(a,b) => is ancestor of(a,b)",
                            "works as(a, farmer|miner) & lives in(a,s) & produces(s,r) => harvests(a,r)"]
DECOY_RULES = [("C", "is child of", "lives in", "lives in"), ("C", "trades with", "is from", "is from"),
               ("C", "mentors", "works as", "works as")]

def generate(seed, scale=1):
    rng = random.Random(seed)
    used = set()
    def name(k=3):
        while True:
            s = "".join(rng.choice(SYL) for _ in range(k))
            if s not in used: used.add(s); return s
    NP, NS, NG = 500 * scale, 40 * scale, 12 * scale
    S = [name(3) for _ in range(NS)]; G = [name(2) + "ia" for _ in range(NG)]; I = [name(2) + "guild" for _ in range(4)]
    T = collections.defaultdict(set)
    # geography
    loc = {s: G[i % NG] for i, s in enumerate(S)}
    for s, g in loc.items(): T["is located in"].add((s, g)); T["contains"].add((g, s))
    for i, g in enumerate(G):
        for h in {G[(i + 1) % NG], rng.choice(G)} - {g}: T["borders"] |= {(g, h), (h, g)}
    prod = {s: set(rng.sample(RESOURCES, rng.choice([1, 2]))) for s in S}
    for s, rs in prod.items():
        for r in rs: T["produces"].add((s, r)); T["exports"].add((loc[s], r))
    overseen = {f: I[i // 2] for i, f in enumerate(PROFESSIONS)}
    for f, inst in overseen.items(): T["is overseen by"].add((f, inst))
    # people in three generations, families of two parents
    sizes = [int(NP * 0.2), int(NP * 0.32)]; sizes.append(NP - sum(sizes))
    gens, lives, works = [], {}, {}
    gens.append([name() for _ in range(sizes[0])])
    for p in gens[0]: lives[p] = rng.choice(S); works[p] = rng.choice(PROFESSIONS)
    parents = {}
    for gi in (1, 2):
        prev = gens[-1][:]; rng.shuffle(prev); couples = [(prev[i], prev[i + 1]) for i in range(0, len(prev) - 1, 2)]
        kids = []
        while len(kids) < sizes[gi]:
            c = rng.choice(couples); k = name(); kids.append(k); parents[k] = c
            lives[k] = lives[c[0]] if rng.random() < 0.8 else rng.choice(S)        # decoy correlation
            works[k] = rng.choice(PROFESSIONS)
        gens.append(kids)
    people = [p for g in gens for p in g]
    for k, (a, b) in parents.items():
        for par in (a, b): T["is parent of"].add((par, k)); T["is child of"].add((k, par))
    for p in people:
        x = [p]
        while x:
            nxt = []
            for c in x:
                for par in parents.get(c, ()): T["is ancestor of"].add((par, p)); nxt.append(par)
            x = nxt
    kids_of = collections.defaultdict(list)
    for k, c in parents.items(): kids_of[c].append(k)
    for sib in kids_of.values():
        for a, b in itertools.permutations(sib, 2): T["is sibling of"].add((a, b))
    for p in people:
        T["lives in"].add((p, lives[p])); T["is from"].add((p, loc[lives[p]])); T["works as"].add((p, works[p]))
        if rng.random() >= 0.06: T["is member of"].add((p, overseen[works[p]]))           # 6% exceptions
        if rng.random() < 0.03: T["is member of"].add((p, rng.choice([i for i in I if i != overseen[works[p]]])))
        if works[p] in ("farmer", "miner"):                                                  # conditional rule
            for r in prod[lives[p]]: T["harvests"].add((p, r))
    by_region = collections.defaultdict(list)
    for p in people: by_region[loc[lives[p]]].append(p)
    by_prof = collections.defaultdict(list)
    for p in people: by_prof[works[p]].append(p)
    for p in people:
        for q in rng.sample(people, 3):
            if q != p: T["knows"].add((p, q))                                               # random decoy
        for _ in range(2):
            pool = by_region[loc[lives[p]]] if rng.random() < 0.85 else people             # decoy correlation
            q = rng.choice(pool)
            if q != p: T["trades with"].add((p, q))
    for p in gens[1] + gens[2]:
        older = gens[0] + (gens[1] if p in set(gens[2]) else [])
        pool = [q for q in older if works[q] == works[p]] if rng.random() < 0.9 else older  # decoy correlation
        if pool: T["mentors"].add((rng.choice(pool), p))
    entities = {"individual": people, "settlement": S, "region": G, "profession": PROFESSIONS, "resource": RESOURCES, "institution": I}
    return {k: sorted(v) for k, v in T.items()}, entities

def observe(truth, entities, seed, coverage, noise=0.03, contradict=0.01, n_unseen=25, n_sparse=50):
    """Sample observations. Returns (lines, info). info is hidden: it says what was withheld and what was corrupted."""
    rng = random.Random(seed * 1000 + int(coverage * 100))
    people = list(entities["individual"]); rng.shuffle(people)
    unseen, sparse = set(people[:n_unseen]), set(people[n_unseen:n_unseen + n_sparse])
    typ = {e: t for t, es in entities.items() for e in es}
    obs, wrong = set(), []
    for pred, facts in truth.items():
        for a, b in facts:
            if a in unseen or b in unseen: continue
            if a in sparse and pred not in ("lives in", "works as"): continue             # sparse: only two facts each
            if a in sparse or rng.random() < coverage: obs.add((pred, a, b))
    functional = ["lives in", "works as", "is located in"]
    rng2 = random.Random(seed * 7 + int(coverage * 100))
    for pred in functional:                                                                 # deliberately incorrect facts
        cands = sorted(f for f in obs if f[0] == pred)
        for f in rng2.sample(cands, int(noise * len(cands))):
            pool = [e for e in entities[typ[f[2]]] if e != f[2]]
            bad = (pred, f[1], rng2.choice(pool)); obs.discard(f); obs.add(bad); wrong.append(list(bad) + ["replaced", f[2]])
    cands = sorted(f for f in obs if f[0] == "lives in")                                     # contradictions: second value added
    for f in rng2.sample(cands, int(contradict * len(cands))):
        bad = ("lives in", f[1], rng2.choice([s for s in entities["settlement"] if s != f[2]]))
        obs.add(bad); wrong.append(list(bad) + ["added", f[2]])
    lines = [f"{a} {p} {b}" for p, a, b in sorted(obs)]
    rng.shuffle(lines)
    return lines, {"unseen": sorted(unseen), "sparse": sorted(sparse), "wrong": wrong, "observed": sorted([list(f) for f in obs])}
