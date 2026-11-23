#!/usr/bin/env python3
"""Sealed confirmation-world generator (independent of the development worlds).

Usage:
    python3 gen_sealed.py STRUCTURE SEED OUTDIR [key=value ...]
    python3 gen_sealed.py --check            # self-check every structure, seeds 0..2

world(structure, seed, **params) -> (lines, key)

Every truth fact is in exactly one of three states:
  stated         -> appears as a line in facts.txt
  hidden         -> absent from facts.txt, determinable from it via the world's rules
  undeterminable -> absent from facts.txt and NOT determinable (listed as [rel, subj])
Corrupted lines are stated but false; the corresponding right fact is hidden.
"""
import json
import os
import random
import re
import sys

TOKEN_RE = re.compile(r"^[A-Za-z0-9_]+$")
REL_RE = re.compile(r"^[a-z]+( [a-z]+)*$")

# ---------------------------------------------------------------- names
_CONS = "bdfgklmnprstvz"
_VOWS = "aeiou"
_TEMPLATES = ["CVC", "CVCV", "CVCVC", "VCVC", "CVVC"]


# Common English words that the templates can produce; rejected as name stems.
_ENGLISH = set("""
bad bag ban bat bed beg bet bid big bin bit bob bod bog bud bug bun bus dab dad dam
den dig dim din dip dog dot dub dud dug fad fan fat fed fen fig fin fit fog fun fur
gab gag gap gas gel gem get gig gin god got gum gun gut kid kin kit lab lad lag lap
led leg let lid lip lit log lot lug mad man map mat men met mid mob mod mom mop mud
mug mum nab nag nap net nil nip nod nor not nun nut pad pal pan pat peg pen pep pet
pig pin pit pod pop pot pub pun pup pus put rag ram ran rap rat red rib rid rig rim
rip rob rod rot rub rug rum run rut sad sag sap sat set sin sip sir sit sob sod son
sop sot sub sum sun sup tab tag tan tap tar ten tin tip ton top tot tub tug van vat
vet zap zen zip bike bake bale bone bore code cone dame date dire dole dome done dune
fake fame fare file fine fire five fume fuse gale game gate gave gene gone kite lake
lame lane late lime line live lobe lone lore lose love lure made make male mane mare
mate mile mine mire mode mole more mule mute name nape nine node none nose note pane
pile pine pipe poke pole pose rake rate ride rife rile ripe robe rode role rope rose
rule safe sake sale same sane site sole some sore sure take tale tame tape tile time
tone tore tube tune vale vane vile vine vote wade zone pure base vise tide side bide
omit edit emit item idol oven over open even avid evil unit unto amid atom alas akin
abet apex onus opus elan oral idle
robin melon lemon bison basin rapid solid timid vivid tumor motor rotor sonar lunar
radar pilot talon salon baton demon lever liver never fever seven given riven raven
token taken laden lemur debut panel model level novel bagel camel label medal pedal
metal total petal satin robot divan
""".split())


class Namer:
    """Pronounceable-but-meaningless tokens; always carry a digit suffix, so
    they can never be English words and never collide with relation words."""

    def __init__(self, rng):
        self.rng = rng
        self.used = set()

    def one(self):
        for _ in range(10000):
            t = self.rng.choice(_TEMPLATES)
            s = "".join(self.rng.choice(_CONS if c == "C" else _VOWS) for c in t)
            if s in _ENGLISH:
                continue
            s += str(self.rng.randint(0, 9))
            if self.rng.random() < 0.25:
                s += str(self.rng.randint(0, 9))
            if s not in self.used:
                self.used.add(s)
                return s
        raise RuntimeError("name space exhausted")

    def many(self, n):
        return [self.one() for _ in range(n)]


# ---------------------------------------------------------------- world builder
class World:
    def __init__(self, structure, seed, params):
        self.structure = structure
        self.seed = seed
        self.params = params
        self.rng = random.Random(f"sealed:{structure}:{seed}")
        self.names = Namer(random.Random(f"names:{structure}:{seed}"))
        self.state = {}          # (rel, s, o) -> "stated" | "hidden" | "undet"
        self.corrupt_lines = []  # (rel, s, wrong, right)
        self.rels = []
        self.rules = []
        self.conditions = []

    def rel(self, phrase):
        assert REL_RE.match(phrase), phrase
        if phrase not in self.rels:
            self.rels.append(phrase)
        return phrase

    def add(self, rel, s, o, mode="stated"):
        assert mode in ("stated", "hidden", "undet")
        f = (rel, s, o)
        if f in self.state and self.state[f] != mode:
            # stated wins over hidden wins over undet
            order = {"stated": 0, "hidden": 1, "undet": 2}
            mode = min(mode, self.state[f], key=order.get)
        self.state[f] = mode

    def corrupt(self, rel, s, wrong, right):
        self.corrupt_lines.append((rel, s, wrong, right))
        self.add(rel, s, right, "hidden")

    def split(self, items, frac_hidden):
        """Seeded split of items into (stated, hidden) with round(frac*n) hidden."""
        items = list(items)
        self.rng.shuffle(items)
        k = int(round(frac_hidden * len(items)))
        return items[k:], items[:k]

    def finish(self):
        stated = [f for f, m in self.state.items() if m == "stated"]
        lines = [f"{s} {r} {o}" for (r, s, o) in stated]
        lines += [f"{s} {r} {w}" for (r, s, w, _) in self.corrupt_lines]
        lines = sorted(set(lines))
        random.Random(f"order:{self.structure}:{self.seed}").shuffle(lines)

        seen = set()
        for (r, s, o) in stated:
            seen.update((s, o))
        for (r, s, w, _) in self.corrupt_lines:
            seen.update((s, w))
        truth_ents = set()
        for (r, s, o) in self.state:
            truth_ents.update((s, o))

        undet = sorted({(r, s) for (r, s, o), m in self.state.items() if m == "undet"})
        key = {
            "structure": self.structure,
            "seed": self.seed,
            "params": self.params,
            "relations": list(self.rels),
            "truth": [list(f) for f in sorted(self.state)],
            "hidden": [list(f) for f in sorted(f for f, m in self.state.items() if m == "hidden")],
            "undeterminable": [list(x) for x in undet],
            "unseen": sorted(truth_ents - seen),
            "corrupted": [list(c) for c in sorted(self.corrupt_lines)],
            "rules": self.rules,
            "conditions": self.conditions,
        }
        return lines, key


def zipf_weights(n, s):
    return [1.0 / (r + 1) ** s for r in range(n)]


def assign_cover(rng, items, targets, weights=None):
    """Map every item to one target; every target gets at least one item
    (requires len(items) >= len(targets)); remaining items by weight."""
    items = list(items)
    rng.shuffle(items)
    out = {}
    for t, it in zip(targets, items):
        out[it] = t
    for it in items[len(targets):]:
        out[it] = rng.choices(targets, weights=weights)[0] if weights else rng.choice(targets)
    return out


# ---------------------------------------------------------------- structures
def g_inverse(w, n_clients=400, n_desks=120, min_links=2, max_links=4, hide=0.3):
    R = w.rel("is served by")
    S = w.rel("serves")
    clients, desks = w.names.many(n_clients), w.names.many(n_desks)
    pairs = []
    for c in clients:
        for d in w.rng.sample(desks, w.rng.randint(min_links, max_links)):
            pairs.append((c, d))
            w.add(R, c, d)
    st, hd = w.split(pairs, hide)
    for c, d in st:
        w.add(S, d, c)
    for c, d in hd:
        w.add(S, d, c, "hidden")
    w.rules.append(f"inverse: X '{R}' Y <=> Y '{S}' X. All '{R}' stated; "
                   f"'{S}' stated for {1-hide:.0%}, rest hidden.")


def g_symmetric(w, n_entities=500, n_pairs=1200, hide=0.3):
    P = w.rel("is paired with")
    ents = w.names.many(n_entities)
    pairs = set()
    while len(pairs) < n_pairs:
        a, b = w.rng.sample(ents, 2)
        if (b, a) not in pairs:
            pairs.add((a, b))
    pairs = sorted(pairs)
    for a, b in pairs:
        w.add(P, a, b)
    st, hd = w.split(pairs, hide)
    for a, b in st:
        w.add(P, b, a)
    for a, b in hd:
        w.add(P, b, a, "hidden")
    w.rules.append(f"symmetric: X '{P}' Y <=> Y '{P}' X. One direction stated for every pair; "
                   f"reverse stated for {1-hide:.0%}, rest hidden.")


def g_transitive(w, n_zones=5, regions_per=(3, 5), places_per=(4, 6), items_per=(5, 7), hide=0.3):
    W_ = w.rel("is within")
    parent = {}
    zones = w.names.many(n_zones)
    regions, places, items = [], [], []
    for z in zones:
        for r in w.names.many(w.rng.randint(*regions_per)):
            parent[r] = z
            regions.append(r)
    for r in regions:
        for p in w.names.many(w.rng.randint(*places_per)):
            parent[p] = r
            places.append(p)
    for p in places:
        for i in w.names.many(w.rng.randint(*items_per)):
            parent[i] = p
            items.append(i)
    indirect = []
    for x in parent:
        w.add(W_, x, parent[x])
        a = parent.get(parent[x])
        while a is not None:
            indirect.append((x, a))
            a = parent.get(a)
    st, hd = w.split(indirect, hide)
    for x, a in st:
        w.add(W_, x, a)
    for x, a in hd:
        w.add(W_, x, a, "hidden")
    w.rules.append(f"transitive: X '{W_}' Y and Y '{W_}' Z => X '{W_}' Z. 4-level hierarchy "
                   f"(item < place < region < zone). All direct links stated; "
                   f"{1-hide:.0%} of indirect links stated, rest hidden.")


def _composition(w, n_x, n_y, n_z, hide, zipf=None, noise=0.0, grades=None, ambiguous=0):
    A = w.rel("is attached to")
    B = w.rel("is housed in")
    C = w.rel("is stationed in")
    xs, ys, zs = w.names.many(n_x), w.names.many(n_y), w.names.many(n_z)
    amb = []
    if grades:
        K = w.rel("is graded")
        gvals = w.names.many(grades)
        # Reuse grade tokens as entities in other roles.
        roles = [("x", xs), ("y", ys), ("z", zs)]
        for i in range(min(ambiguous, len(gvals))):
            role, lst = roles[i % 3]
            j = w.rng.randrange(len(lst))
            lst[j] = gvals[i]
            amb.append((gvals[i], role))
    yw = zipf_weights(n_y, zipf) if zipf else None
    zw = zipf_weights(n_z, zipf) if zipf else None
    x2y = assign_cover(w.rng, xs, ys, yw)
    y2z = assign_cover(w.rng, ys, zs, zw)
    for x, y in x2y.items():
        w.add(A, x, y)
    for y, z in y2z.items():
        w.add(B, y, z)
    st, hd = w.split(xs, hide)
    for x in hd:
        w.add(C, x, y2z[x2y[x]], "hidden")
    n_noise = int(round(noise * len(st)))
    noisy = set(w.rng.sample(st, n_noise)) if n_noise else set()
    for x in st:
        right = y2z[x2y[x]]
        if x in noisy:
            wrong = w.rng.choice([z for z in zs if z != right])
            w.corrupt(C, x, wrong, right)
        else:
            w.add(C, x, right)
    w.rules.append(f"composition: X '{A}' Y and Y '{B}' Z => X '{C}' Z ('{C}' has one value per X). "
                   f"All '{A}' and '{B}' stated; '{C}' stated for {1-hide:.0%} of X, rest hidden.")
    if noise:
        w.rules.append(f"noise: {n_noise} of the stated '{C}' facts ({noise:.0%}) carry a wrong object; "
                       f"they are listed in 'corrupted' and the right fact is in 'hidden'.")
    if zipf:
        cnt = {}
        for y in x2y.values():
            cnt[y] = cnt.get(y, 0) + 1
        top = sorted(cnt.values(), reverse=True)[:5]
        w.rules.append(f"hub: '{A}' targets and '{B}' targets drawn with Zipf weights (s={zipf}); "
                       f"top Y in-degrees {top}.")
    if grades:
        for x in xs:
            w.add(K, x, w.rng.choice(gvals))
        w.rules.append(f"attribute: every X '{K}' one of {len(gvals)} values; irrelevant to the composition rule.")
        for tok, role in amb:
            w.rules.append(f"ambiguous: token '{tok}' is a value of '{K}' and also an entity in role {role} "
                           f"of the composition (role x: subject of '{A}'; y: object of '{A}'/subject of '{B}'; "
                           f"z: object of '{B}'/'{C}').")


def g_composition(w, n_x=800, n_y=100, n_z=15, hide=0.3):
    _composition(w, n_x, n_y, n_z, hide)


def g_noise(w, n_x=800, n_y=100, n_z=15, hide=0.3, noise=0.15):
    _composition(w, n_x, n_y, n_z, hide, noise=noise)


def g_hub(w, n_x=2000, n_y=150, n_z=20, hide=0.3, zipf=1.1):
    _composition(w, n_x, n_y, n_z, hide, zipf=zipf)


def g_ambiguous(w, n_x=800, n_y=100, n_z=15, hide=0.3, grades=6, ambiguous=3):
    _composition(w, n_x, n_y, n_z, hide, grades=grades, ambiguous=ambiguous)


def g_path3(w, n_families=60, branch=(2, 3), example_families=0.5, hide=0.3):
    A = w.rel("is sponsor of")
    D = w.rel("is great sponsor of")
    fams = []
    for _ in range(n_families):
        gens = [[w.names.one()]]
        for _g in range(3):
            nxt = []
            for p in gens[-1]:
                for c in w.names.many(w.rng.randint(*branch)):
                    w.add(A, p, c)
                    nxt.append(c)
            gens.append(nxt)
        fams.append(gens)
    order = list(range(n_families))
    w.rng.shuffle(order)
    n_ex = int(round(example_families * n_families))
    ex = set(order[:n_ex])
    n_st = 0
    for i, gens in enumerate(fams):
        # the only 3-step paths in a 4-generation tree run root -> gen3
        root = gens[0][0]
        conc = [(root, d) for d in gens[3]]
        if i in ex:
            st, hd = w.split(conc, hide)
        else:
            st, hd = [], conc
        for a, d in st:
            w.add(D, a, d)
            n_st += 1
        for a, d in hd:
            w.add(D, a, d, "hidden")
    w.rules.append(f"path3: X '{A}' Y and Y '{A}' Z and Z '{A}' V => X '{D}' V. {n_families} 4-generation "
                   f"families; '{D}' examples only in {n_ex} families ({1-hide:.0%} of their conclusions, "
                   f"{n_st} lines); all other '{D}' facts hidden.")


def _conditional(w, mode, n_x=1000, n_y=80, n_z=12, n_categories=8, qualifying=2, stated=0.85,
                 n_decoys=3, decoy_values=6, decoy_share=0.6):
    K = w.rel("is classed")
    A = w.rel("operates")
    B = w.rel("is filed under")
    C = w.rel("is assigned")
    xs, ys, zs = w.names.many(n_x), w.names.many(n_y), w.names.many(n_z)
    cats = w.names.many(n_categories)
    if isinstance(qualifying, int):
        qual = sorted(w.rng.sample(cats, qualifying))
    else:
        qual = sorted(qualifying)
    xcat = assign_cover(w.rng, xs, cats)
    x2y = assign_cover(w.rng, xs, ys)
    y2z = assign_cover(w.rng, ys, zs)
    for x in xs:
        w.add(K, x, xcat[x])
        w.add(A, x, x2y[x])
    for y, z in y2z.items():
        w.add(B, y, z)
    if mode == "control":
        holders = list(xs)
    else:
        holders = [x for x in xs if xcat[x] in qual]
    st, hd = w.split(holders, 1 - stated)
    for x in st:
        w.add(C, x, y2z[x2y[x]])
    for x in hd:
        w.add(C, x, y2z[x2y[x]], "hidden")
    rule = f"X '{A}' Y and Y '{B}' Z => X '{C}' Z"
    if mode == "control":
        w.rules.append(f"{rule}, for EVERY X (no condition). '{K}' present but irrelevant. "
                       f"'{C}' stated for {stated:.0%} of X, rest hidden.")
    else:
        w.rules.append(f"{rule}, ONLY for X whose '{K}' value is in {qual}. '{C}' stated for "
                       f"{stated:.0%} of qualifying X, rest hidden; '{C}' never holds for non-qualifying X "
                       f"(absent from truth = false).")
        w.conditions.append({"rule": rule, "condition_relation": K, "qualifying_values": qual})
    if mode == "decoy":
        drels = [w.rel(p) for p in ["is tagged", "is banded", "is keyed", "is marked", "is sorted"][:n_decoys]]
        corr = w.rng.randrange(len(drels))
        qset = set(holders)
        for i, dr in enumerate(drels):
            vals = w.names.many(decoy_values)
            star = w.rng.choice(vals)
            hits = 0
            for x in xs:
                if i == corr and x in qset:
                    v = star if w.rng.random() < decoy_share else w.rng.choice([u for u in vals if u != star])
                    hits += v == star
                else:
                    v = w.rng.choice(vals)
                w.add(dr, x, v)
            if i == corr:
                others = [x for x in xs if x not in qset]
                share_o = sum(1 for x in others if (dr, x, star) in w.state) / max(1, len(others))
                w.rules.append(f"decoy (chance-correlated, NOT causal): '{dr}' value '{star}' held by "
                               f"{hits/len(qset):.0%} of qualifying X vs {share_o:.0%} of others.")
            else:
                w.rules.append(f"decoy (random, unrelated): '{dr}', {decoy_values} values, uniform.")


def g_conditional(w, **kw):
    _conditional(w, "cond", **kw)


def g_conditional_control(w, **kw):
    _conditional(w, "control", **kw)


def g_conditional_decoy(w, **kw):
    _conditional(w, "decoy", **kw)


_GATE_FUNCS = {"and": lambda a, b: a & b, "or": lambda a, b: a | b, "xor": lambda a, b: a ^ b}


def g_branching(w, n_gates=400, stated=0.65):
    KIND = w.rel("is of kind")
    IN1 = w.rel("reads first")
    IN2 = w.rel("reads second")
    OUT = w.rel("feeds")
    VAL = w.rel("holds")
    kinds = dict(zip(_GATE_FUNCS, w.names.many(3)))
    lo, hi = w.names.many(2)
    tok = {0: lo, 1: hi}
    gates = []
    for _ in range(n_gates):
        g, a, b, o = w.names.many(4)
        fn = w.rng.choice(sorted(_GATE_FUNCS))
        va, vb = w.rng.randint(0, 1), w.rng.randint(0, 1)
        w.add(KIND, g, kinds[fn])
        w.add(IN1, g, a)
        w.add(IN2, g, b)
        w.add(OUT, g, o)
        w.add(VAL, a, tok[va])
        w.add(VAL, b, tok[vb])
        gates.append((o, tok[_GATE_FUNCS[fn](va, vb)]))
    st, hd = w.split(gates, 1 - stated)
    for o, v in st:
        w.add(VAL, o, v)
    for o, v in hd:
        w.add(VAL, o, v, "hidden")
    desc = ", ".join(f"'{kinds[f]}'={f}" for f in sorted(kinds))
    w.rules.append(f"branching: gate G '{KIND}' K, G '{IN1}' A, G '{IN2}' B, G '{OUT}' O; "
                   f"O '{VAL}' f_K(value(A), value(B)), values '{lo}'=0 '{hi}'=1; kinds {desc}. "
                   f"Output values stated for {stated:.0%} of gates, rest hidden.")


_NUMWORD = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}


def g_depth(w, N=1500, k=3, given=0.5):
    L = w.rel(f"is {_NUMWORD[k]} steps past")
    P = w.rel("is phased")
    nums = w.names.many(N + 1)
    phases = w.names.many(k)
    for i in range(k, N + 1):
        w.add(L, nums[i], nums[i - k])
    idx = list(range(N + 1))
    w.rng.shuffle(idx)
    giv = set(idx[: int(round(given * (N + 1)))])
    lowest = {}
    for i in range(N + 1):
        r = i % k
        if i in giv:
            w.add(P, nums[i], phases[r])
            lowest.setdefault(r, i)
        elif r in lowest:
            w.add(P, nums[i], phases[r], "hidden")
        else:
            w.add(P, nums[i], phases[r], "undet")
    w.rules.append(f"depth: n_(i+{k}) '{L}' n_i over n_0..n_{N}; '{P}' has period {k} along these links "
                   f"(X '{L}' Y => X '{P}' same value as Y). '{P}' given for {given:.0%}; hidden = members "
                   f"with a given member below in steps of {k}; undeterminable = those with none below "
                   f"(by definition of this study, upward inference is not counted).")


def g_control(w, n_entities=400, links_per_relation=800):
    rels = [w.rel("is linked to"), w.rel("is flagged by"), w.rel("is routed to")]
    ents = w.names.many(n_entities)
    for r in rels:
        n = 0
        while n < links_per_relation:
            a, b = w.rng.sample(ents, 2)
            if (r, a, b) not in w.state:
                w.add(r, a, b)
                n += 1
    w.rules.append(f"control: random links in {rels}; no generating rule; truth = stated facts only.")


STRUCTURES = {
    "inverse": g_inverse, "symmetric": g_symmetric, "transitive": g_transitive,
    "composition": g_composition, "path3": g_path3, "conditional": g_conditional,
    "conditional_control": g_conditional_control, "conditional_decoy": g_conditional_decoy,
    "branching": g_branching, "depth": g_depth, "noise": g_noise, "control": g_control,
    "hub": g_hub, "ambiguous": g_ambiguous,
}


def _defaults(fn):
    import inspect
    if fn in (g_conditional, g_conditional_control, g_conditional_decoy):
        fn = _conditional
    return {k: v.default for k, v in inspect.signature(fn).parameters.items()
            if v.default is not inspect.Parameter.empty}


def world(structure, seed, **params):
    if structure not in STRUCTURES:
        raise ValueError(f"unknown structure {structure}; choose from {sorted(STRUCTURES)}")
    fn = STRUCTURES[structure]
    eff = _defaults(fn)
    if structure != "conditional_decoy":
        for k in ("n_decoys", "decoy_values", "decoy_share"):
            eff.pop(k, None)
    unknown = set(params) - set(eff)
    if unknown:
        raise ValueError(f"unknown params for {structure}: {sorted(unknown)}")
    eff.update(params)
    eff = {k: (list(v) if isinstance(v, tuple) else v) for k, v in eff.items()}
    w = World(structure, seed, eff)
    call = {k: (tuple(v) if isinstance(v, list) and k in ("regions_per", "places_per", "items_per", "branch") else v)
            for k, v in eff.items()}
    fn(w, **call)
    return w.finish()


# ---------------------------------------------------------------- self-check
def check(lines, key):
    rels = sorted(key["relations"], key=len, reverse=True)
    assert len(set(rels)) == len(rels), "duplicate relations"
    for r in rels:
        assert REL_RE.match(r), f"bad relation phrase {r!r}"
    assert len(set(lines)) == len(lines), "duplicate lines"
    truth = {tuple(f) for f in key["truth"]}
    hidden = {tuple(f) for f in key["hidden"]}
    corrupted = {(r, s, w) for (r, s, w, _) in key["corrupted"]}
    rights = {(r, s, o) for (r, s, _, o) in key["corrupted"]}
    parsed = set()
    used = set()
    ents = set()
    for ln in lines:
        toks = ln.split(" ")
        assert len(toks) >= 3, ln
        s, o, r = toks[0], toks[-1], " ".join(toks[1:-1])
        assert TOKEN_RE.match(s) and TOKEN_RE.match(o), f"bad token in {ln!r}"
        assert r in key["relations"], f"relation not listed: {ln!r}"
        assert not any(c.isdigit() for c in r)
        parsed.add((r, s, o))
        used.add(r)
        ents.update((s, o))
    for f in parsed:
        if f not in corrupted:
            assert f in truth, f"stated fact not in truth: {f}"
        else:
            assert f not in truth, f"corrupted fact in truth: {f}"
    assert corrupted <= parsed
    assert rights <= hidden
    assert not (hidden & parsed), "hidden fact appears in facts"
    assert hidden <= truth
    for r, s, o in truth:
        used.add(r)
        assert TOKEN_RE.match(s) and TOKEN_RE.match(o)
    assert used == set(key["relations"]), "relations list incomplete or has extras"
    und = {tuple(x) for x in key["undeterminable"]}
    und_facts = {f for f in truth if (f[0], f[1]) in und}
    assert truth == (parsed - corrupted) | hidden | und_facts, "truth not partitioned"
    assert not (und_facts & (parsed | hidden))
    truth_ents = {e for (_, s, o) in truth for e in (s, o)}
    assert set(key["unseen"]) == truth_ents - ents
    for c in key["conditions"]:
        q = set(c["qualifying_values"])
        kval = {s: o for (r, s, o) in truth if r == c["condition_relation"]}
        crel = c["rule"].split("=> X '")[1].split("'")[0]
        for (r, s, o) in truth:
            if r == crel:
                assert kval[s] in q, f"conditional conclusion for non-qualifying {s}"
    return True


def _main(argv):
    if argv and argv[0] == "--check":
        for st in STRUCTURES:
            for sd in range(3):
                lines, key = world(st, sd)
                check(lines, key)
                again, key2 = world(st, sd)
                assert again == lines and key2 == key, "not deterministic"
                print(f"{st:20s} seed {sd}: {len(lines):5d} lines, truth {len(key['truth']):5d}, "
                      f"hidden {len(key['hidden']):5d}, undet {len(key['undeterminable']):4d}, "
                      f"corrupted {len(key['corrupted']):3d}, unseen {len(key['unseen'])}")
        print("all checks passed")
        return 0
    if len(argv) < 3:
        print(__doc__)
        return 2
    st, sd, out = argv[0], int(argv[1]), argv[2]
    params = {}
    for kv in argv[3:]:
        k, v = kv.split("=", 1)
        try:
            params[k] = json.loads(v)
        except json.JSONDecodeError:
            params[k] = v
    lines, key = world(st, sd, **params)
    check(lines, key)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "facts.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "key.json"), "w") as f:
        json.dump(key, f, indent=1)
    print(f"wrote {len(lines)} lines to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
