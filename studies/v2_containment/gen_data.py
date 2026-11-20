"""Writes every dataset used to compare Voltex v1 and v2 (deterministic seeds)."""
import random, itertools, json, os
os.makedirs("data", exist_ok=True)

# 1. EVO JSON: same record format as voltex_paged.cpp generateDummyJson
def dummy_json(i, rng):
    eye = ["blue", "brown", "green", "amber", "gray"]; fr = ["apple", "banana", "strawberry", "mango", "kiwi"]
    dp = ["NEURAL_BIO", "CYBER_LOGIC", "QUANTUM_OPS", "VOLTEX_LABS"]
    return ('{"_id":"5f%06x%06x","index":%d,"isActive":%s,"balance":"$%.2f","age":%d,"eyeColor":"%s",'
            '"name":"Agent_%d","company":"%s","location":[%.4f,%.4f],"favoriteFruit":"%s"}') % (
        rng.randrange(0xFFFFFF), rng.randrange(0xFFFFFF), i, "true" if rng.random() < .5 else "false",
        1000 + rng.randrange(500000) / 100, 18 + rng.randrange(50), rng.choice(eye), i, rng.choice(dp),
        rng.randrange(1800000) / 10000 - 90, rng.randrange(3600000) / 10000 - 180, rng.choice(fr))
rng = random.Random(1)
for n in (1000, 20000):
    with open(f"data/evo_{n}.txt", "w") as f:
        for i in range(1, n + 1): f.write(dummy_json(i, rng) + "\n")

# 2. Natural text: license files, one line per record
lines = [l.rstrip("\n") for fn in ["GPL-3", "Apache-2.0", "GFDL-1.3", "GPL-2", "Artistic", "LGPL-3", "LGPL-2.1", "MPL-2.0"]
         if os.path.exists(f"/usr/share/common-licenses/{fn}")
         for l in open(f"/usr/share/common-licenses/{fn}", encoding="utf-8", errors="ignore") if 8 < len(l.strip()) < 200]
open("data/license.txt", "w").write("\n".join(lines) + "\n")

# 3. Synthetic grammar with held-out ADJ-NOUN pairs (identical generator to exp2_counters.py)
g = random.Random(7)
LEX = {"NAME": "ana bo cyr dax eli fen gus hal ivo jun".split(), "VERB": "carries paints sells finds drops fixes".split(),
       "ADJ": "red blue old tiny heavy shiny broken green".split(), "NOUN": "lamp chair kettle drum rope vase clock mirror sled bowl".split(),
       "VINT": "rests waits sits glows hides".split(), "PREP": "in near under".split(),
       "PLACE": "barn kitchen garden cellar attic market shed harbor".split()}
T = [["NAME", "VERB", "the", "ADJ", "NOUN", "PREP", "the", "PLACE", "."], ["the", "ADJ", "NOUN", "VINT", "PREP", "the", "PLACE", "."],
     ["NAME", "VINT", "PREP", "the", "PLACE", "."]]
pairs = list(itertools.product(LEX["ADJ"], LEX["NOUN"])); g.shuffle(pairs); held = set(pairs[:int(0.3 * len(pairs))])
def sample(req=None):
    while True:
        t = g.choice(T[:2] if req is not None else T); s = [g.choice(LEX[x]) if x in LEX else x for x in t]
        if "ADJ" in t:
            i = t.index("ADJ"); p = (s[i], s[i + 1])
            if req is True and p not in held: continue
            if req is None and p in held: continue
        return s
train = [sample() for _ in range(3000)]; unseen = [sample(True) for _ in range(300)]; seen = [sample() for _ in range(300)]
for name, d in [("grammar_train", train), ("grammar_unseen", unseen), ("grammar_seen", seen)]:
    open(f"data/{name}.txt", "w").write("\n".join(" ".join(s) for s in d) + "\n")
json.dump({"held": sorted(held)}, open("data/grammar_held.json", "w"))

# 4. Inference world: a containment hierarchy + a non-transitive control relation
w = random.Random(11)
syll = ["ka", "lo", "mi", "ne", "ru", "sa", "ti", "vo", "ze", "pa", "do", "fi", "gu", "he", "jo", "be"]
used = set()
def name():
    while True:
        s = "".join(w.choice(syll) for _ in range(3))
        if s not in used: used.add(s); return s
towns = [name() for _ in range(4)]
buildings = {t: [name() for _ in range(3)] for t in towns}
rooms = {b: [name() for _ in range(3)] for t in towns for b in buildings[t]}
people = {r: [name() for _ in range(2)] for b in rooms for r in rooms[b]}
parent = {}
for t in towns:
    for b in buildings[t]:
        parent[b] = t
        for r in rooms[b]:
            parent[r] = b
            for p in people[r]: parent[p] = r
def ancestors(x):
    out = []
    while x in parent: x = parent[x]; out.append(x)
    return out
base_in = [(c, p) for c, p in parent.items()]
implied_in = [(x, a) for x in parent for a in ancestors(x)[1:]]
w.shuffle(implied_in)
stated_implied, heldout_implied = implied_in[:len(implied_in) // 2], implied_in[len(implied_in) // 2:]
contains_true = [(a, x) for x in parent for a in ancestors(x)]
base_contains = [(p, c) for c, p in parent.items()]; w.shuffle(base_contains)
stated_contains = base_contains[:len(base_contains) // 2]
everyone = [p for r in people for p in people[r]]
knows = set()
for p in everyone:
    for q in w.sample([x for x in everyone if x != p], 3): knows.add((p, q))
facts = [f"{a} is in {b}" for a, b in base_in + stated_implied] + [f"{a} contains {b}" for a, b in stated_contains] + \
        [f"{a} knows {b}" for a, b in knows]
w.shuffle(facts)
open("data/world_train.txt", "w").write("\n".join(facts) + "\n")
truth = {"is in": sorted(set(base_in + implied_in)), "contains": sorted(set(contains_true)), "knows": sorted(knows),
         "heldout_is_in": sorted(heldout_implied),
         "heldout_contains": sorted(set(contains_true) - set(stated_contains))}
json.dump(truth, open("data/world_truth.json", "w"))
print("records:", {f: sum(1 for _ in open("data/" + f)) for f in sorted(os.listdir("data")) if f.endswith(".txt")})
print("world: stated facts", len(facts), "| held-out is-in", len(heldout_implied), "| held-out contains", len(truth["heldout_contains"]))
