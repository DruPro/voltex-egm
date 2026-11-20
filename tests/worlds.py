"""Small, deterministic worlds for the SDK tests of the experimental settings (seconds to run)."""
import random

OPS = {"xor": lambda a, b: a ^ b, "and": lambda a, b: a & b, "or": lambda a, b: a | b}
WORD = {0: "zero", 1: "one"}


def _names(seed):
    syl = [a + b for a in "bdfgklmnprstvz" for b in "aeiou"]
    pool = [x + y + z for x in syl for y in syl for z in syl[:10]]
    random.Random(seed).shuffle(pool); return iter(pool)


def lineage(families=30, taught=20, seed=1):
    """Parent facts for 4-generation families; great-grandparent given only for the first `taught` families."""
    r = random.Random(seed); it = _names(seed); lines, unseen = [], set()
    for f in range(families):
        gens = [[next(it)]]
        for g in range(1, 4):
            gens.append([])
            for p in gens[g - 1]:
                for _ in range(2):
                    c = next(it); gens[g].append(c); lines.append(f"{p} is parent of {c}")
        for y in gens[3]:
            if f < taught: lines.append(f"{gens[0][0]} is great grandparent of {y}")
            else: unseen.add((gens[0][0], y))
    r.shuffle(lines); return lines, unseen


def gates(per_kind=200, seed=1):
    """Gates of three kinds; outputs given for two thirds. Returns lines and {hidden output wire: value}."""
    r = random.Random(seed); it = _names(seed); lines, hidden = [], {}
    for kind in OPS:
        for _ in range(per_kind):
            g, w1, w2, w3 = next(it), next(it), next(it), next(it); a, b = r.randint(0, 1), r.randint(0, 1)
            lines += [f"{w3} is output of {g}", f"{g} has first input {w1}", f"{g} has second input {w2}", f"{g} has kind {kind}",
                      f"{w1} has value {WORD[a]}", f"{w2} has value {WORD[b]}"]
            if r.random() < 2 / 3: lines.append(f"{w3} has value {WORD[OPS[kind](a, b)]}")
            else: hidden[w3] = WORD[OPS[kind](a, b)]
    r.shuffle(lines); return lines, hidden


def remainders(n=90, seed=0):
    """'is three more than' for all, a decoy 'is one more than', remainders mod 3 for half the numbers."""
    r = random.Random(seed); nums = list(range(n)); r.shuffle(nums); taught = set(nums[: n // 2])
    lines = [f"n{a + 3} is three more than n{a}" for a in range(n - 3)] + [f"n{a + 1} is one more than n{a}" for a in range(n - 1)]
    lines += [f"n{a} has remainder r{a % 3}" for a in sorted(taught)]
    return lines, {f"n{a}": f"r{a % 3}" for a in range(n) if a not in taught}


def harvest(people=400, seed=3):
    """People live in towns that produce goods; only farmers and miners harvest what their town produces.
    Harvest facts are given for 90% of the farmers' and miners' harvests."""
    r = random.Random(seed); it = _names(seed)
    towns = [next(it) for _ in range(20)]; goods = [next(it) for _ in range(12)]
    jobs = ["farmer", "miner", "smith", "healer", "scribe", "weaver", "guard", "merchant"]
    lines = []; produce = {t: r.sample(goods, 2) for t in towns}
    for t in towns:
        for g in produce[t]: lines.append(f"{t} produces {g}")
    wrong = set()
    for _ in range(people):
        p, t, j = next(it), r.choice(towns), r.choice(jobs)
        lines += [f"{p} lives in {t}", f"{p} works as {j}"]
        for g in produce[t]:
            if j in ("farmer", "miner"):
                if r.random() < 0.9: lines.append(f"{p} harvests {g}")
            else: wrong.add((p, g))
    r.shuffle(lines); return lines, wrong
