"""Worlds for studies/shard_general. Each returns (lines, hidden), hidden = {"truth", "corrupted", "relations", ["unseen"]}
for studies/noise/tools/lib.py score(). Only `lines` reach the split and the engines.

  company(seed, scale, noise)      studies/noise generator
  blind(seed, scale)               studies/noise hidden(): the Blind World (coverage 0.5, 3% noise)
  gates(seed, per_kind)            studies/noise gates(), clean
  lineage(seed, families)          family trees; great-grandparent stated for 25 of every 40 families (as gen.lineage)
  realcode(seed, hide)             facts extracted from 125 installed Python packages (data/realcode_facts.txt.xz,
                                   AST truth); a seeded random share `hide` of the facts is held out as the key
"""
import lzma, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "noise", "hidden"))
import gen  # noqa: E402


def company(seed, scale, noise):
    return gen.company(seed=seed, scale=scale, noise=noise)


def blind(seed, scale):
    return gen.hidden(seed=seed, scale=scale, coverage=0.5, noise=0.03)


def gates(seed, per_kind):
    return gen.gates(seed=seed, per_kind=per_kind, noise=0.0)


def lineage(seed, families):
    r = random.Random(6000 + seed)
    syl = ["ka", "mo", "ri", "tu", "se", "ne", "lo", "fa", "di", "ze", "bo", "ja", "vu", "pe", "xi", "go"]
    names = sorted({a + b + c + d for a in syl for b in syl for c in syl for d in syl}); r.shuffle(names); it = iter(names)
    lines, T = [], []
    for f in range(families):
        gens = [[next(it)]]
        for g in range(1, 4):
            gens.append([])
            for p in gens[g - 1]:
                for _ in range(2):
                    c = next(it); gens[g].append(c); lines.append(f"{p} is parent of {c}"); T.append(["is parent of", p, c])
        for y in gens[3]:
            T.append(["is great grandparent of", gens[0][0], y])
            if f % 40 < 25: lines.append(f"{gens[0][0]} is great grandparent of {y}")
    r.shuffle(lines)
    return lines, {"truth": sorted(T), "corrupted": [], "relations": ["is great grandparent of", "is parent of"]}


RELS_CODE = ["is defined in", "calls", "raises", "inherits from", "imports"]


def realcode(seed, hide=0.2):
    with lzma.open(os.path.join(HERE, "..", "data", "realcode_facts.txt.xz"), "rt") as fh:
        facts = [l for l in fh.read().splitlines() if l.strip()]
    r = random.Random(7000 + seed)
    kept = [l for l in facts if r.random() >= hide]
    truth = []
    for l in facts:
        for rel in RELS_CODE:
            k = f" {rel} "
            if k in l:
                a, b = l.split(k, 1); truth.append([rel, a.strip(), b.strip()]); break
    return kept, {"truth": sorted(truth), "corrupted": [], "relations": RELS_CODE}


WORLDS = {"company": company, "blind": blind, "gates": gates, "lineage": lineage, "realcode": realcode}
