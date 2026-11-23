#!/usr/bin/env python3
"""Round 2 sealed world generator (see SPEC.md and README.md in this directory).

    python3 gen_sealed2.py STRUCTURE SEED OUTDIR [key=value ...]   # writes facts.txt, key.json
    python3 gen_sealed2.py --check                                 # self-check, seeds 0..2, determinism

From Python: lines, key = world("graded", 3, noise=[0, 0.1, 0.2, 0.4, 0.6])

Standard library only. Output is a pure function of (structure, seed, params).
"""
import json
import math
import os
import random
import re
import statistics
import sys

# ---------------------------------------------------------------------------
# names

CONS = "bdfgklmnprstvz"
VOWS = "aeiou"
TEMPLATES = ("CVC", "CVCV", "CVCVC", "VCVC", "CVVC")
BLOCKLIST = set("""
bad bag ban bar bat bed beg bet bid big bin bit bog bop bot bud bug bum bun bus but dab dad dam den dig dim din dip
dog don dot dub dud dug fab fad fan far fat fed fen fib fig fin fir fit fog fun fur gab gag gal gap gas gel gem get
gig gin god got gum gun gut keg kid kin kit lab lad lag lap led leg let lid lip lit log lot mad man map mat men met
mid mob mod mom mop mud mug nab nag nap net nib nod nor not nun nut pad pal pan par pat peg pen pep pet pig pin pit
pod pop pot pub pug pun pup pus put rag ram ran rap rat red rib rid rig rim rip rob rod rot rub rug rum run rut sad
sag sap sat set sin sip sir sit sob sod son sop sub sum sun tab tad tag tan tap tar ten tin tip ton top tot tub tug
tun van vat vet zap zen zip
babe bake bale bane bare base bide bike bile bite bode bole bone bore bube dame dare date dene dime dine dire dive
dome done dope dose dote dune dupe fade fake fame fare fate fide file fine fire fume fuse gale game gape gate gave
gene gone kale kite lake lame lane late lime line lobe lode lone lore lose lube lune lure lute made make male mane
mare mate meme mere mete mile mine mire mode mole mope more mule muse mute nape nine node none nose note pale pane
pare pave pike pile pine pipe pole pone pope pore pose pure rake rare rate rave ride rife rile rime ripe rise rive
robe rode role rope rose rote rube rude rule rune ruse safe sage sake sale same sane sate save side sine sire site
size sole some sore sure tale tame tape tare tide tile time tine tire tome tone tope tore tote tube tune vane vase
vile vine vise vote zone
bagel basin begin bekon below bezel bison bogus bonus dozen fatal fetal final kebab label lapel lemon level lever
limit liver local lotus lunar mabel madam manor medal melon metal mimic minor model molar moral motel motor nasal
natal never novel panel pedal penal petal pilot pivot polar radar rapid rebel refer relax rival robin robot rotor
rumor ruler salad satin seven sinus solar solid sonar sugar tenor tidal timid token tonal topaz total tumor tutor
valid vapor venom visit vital vocal
abet amid amok anon apex atom avid edit emit evil exam idol item omen open oven ovum undo unit upon urge used
boom boot beef beer bees beet daub dead deaf deal dean dear deed deem deep doom door doze fail fear feat feed feel
feet foal foam food fool foot fuel gaol gear goad goal goat good keel keen keep kiss laid lain lead leaf leak lean
leap lied lies lion load loaf loan loom loop loot maid mail main meal mean meat meek meet moan mood moon moor moot
need noon pail pain pair peak peal pear peat peek peel peer pied poem poet pool poor raid rail rain read real reap
rear reed reef reek reel road roam roar room root ruin sail seal seam sear seat seed seek seem seen seep soak soap
soar soil soon soot soup tail teal team tear teem teen tied toad toil tool toot veil vein void zeal zoom
""".split())

NAME_RE = re.compile(r"^(?:[%s][%s][%s]|[%s][%s][%s][%s]|[%s][%s][%s][%s][%s]|[%s][%s][%s][%s]|[%s][%s][%s][%s])"
                     r"(?:[1-9][0-9]?)$" % ((CONS, VOWS, CONS) + (CONS, VOWS, CONS, VOWS)
                                            + (CONS, VOWS, CONS, VOWS, CONS) + (VOWS, CONS, VOWS, CONS)
                                            + (CONS, VOWS, VOWS, CONS)))
REL_RE = re.compile(r"^[a-z]+(?: [a-z]+)*$")

# relation phrases chosen per world (fixed phrases named in SPEC.md are added explicitly)
REL_POOL = """links to|feeds|serves|holds|joins|owns|keeps|guards|visits|follows|trusts|sends|marks|greets|backs|
hosts|tends|pairs with|leans on|points to|draws from|answers to|reports to|sits near|waits for|calls on|binds|shapes|
mirrors|echoes|covers|lifts|steers|bears|fetches|claims|grants|rests on|borrows from|tracks|is filed with|admits|
favors|lends to|watches|is tied to|rides with|is kept by|pulls|is sent to|ranks with|is near|is linked with""".replace(
    "\n", "").split("|")
FIXED_RELS = {"requires", "suggests", "carries", "is under"}

KEY_FIELDS = ["structure", "seed", "params", "relations", "truth", "hidden", "undeterminable", "corrupted", "unseen",
              "rules", "conditions", "rule_quality"]


class World:
    """Accumulates one world: truth facts with a state, corrupted lines, rules."""

    def __init__(self, structure, seed, params):
        self.structure, self.seed, self.params = structure, seed, params
        self.rng = random.Random("sealed2/%s/%d" % (structure, seed))
        self.used = set()
        self.rels = []
        self.single = set()          # one-value-per-subject relations
        self.facts = {}              # (rel, s, o) -> 'S' | 'H' | 'U'   (insertion ordered)
        self.corrupted = []          # [rel, s, wrong, right]
        self.rules = []              # rule dicts (see measure())
        self.conditions = []
        self.pool = [p for p in REL_POOL if p not in FIXED_RELS]
        self.rng.shuffle(self.pool)
        self.checks = []             # (label, measured, expected, tolerance) for check()

    # entities and relations
    def names(self, n):
        out = []
        while len(out) < n:
            t = self.rng.choice(TEMPLATES)
            stem = "".join(self.rng.choice(CONS) if c == "C" else self.rng.choice(VOWS) for c in t)
            if stem in BLOCKLIST:
                continue
            name = stem + str(self.rng.randint(1, 99))
            if name in self.used:
                continue
            self.used.add(name)
            out.append(name)
        return out

    def rel(self, phrase=None, single=True):
        if phrase is None:
            phrase = self.pool.pop()
        assert phrase not in self.rels
        self.rels.append(phrase)
        if single:
            self.single.add(phrase)
        return phrase

    def add(self, r, s, o, state="S"):
        assert state in "SHU"
        k = (r, s, o)
        assert k not in self.facts, k
        self.facts[k] = state

    def corrupt(self, r, s, wrong, right, state="H"):
        self.add(r, s, right, state)
        self.corrupted.append([r, s, wrong, right])

    def rule(self, text, kind, generating=True, **kw):
        d = dict(text=text, kind=kind, generating=generating)
        d.update(kw)
        self.rules.append(d)
        return d

    def pick_stated(self, items, share):
        """Exactly round(share * len(items)) items, chosen at random; returns a set of indices."""
        k = int(round(share * len(items)))
        idx = list(range(len(items)))
        self.rng.shuffle(idx)
        return set(idx[:k])

    # output
    def stated_lines(self):
        out = [k for k, st in self.facts.items() if st == "S"]
        out += [(r, s, w) for r, s, w, _ in self.corrupted]
        return out

    def finalize(self):
        stated = self.stated_lines()
        lines = sorted("%s %s %s" % (s, r, o) for r, s, o in stated)
        self.rng.shuffle(lines)
        truth = sorted([r, s, o] for (r, s, o) in self.facts)
        hidden = sorted([r, s, o] for (r, s, o), st in self.facts.items() if st == "H")
        undet = []
        for (r, s, o), st in self.facts.items():
            if st == "U":
                undet.append([r, s] if r in self.single else [r, s, o])
        undet.sort()
        seen = set()
        for r, s, o in stated:
            seen.add(s)
            seen.add(o)
        ents = set()
        for (r, s, o) in self.facts:
            ents.add(s)
            ents.add(o)
        unseen = sorted(ents - seen)
        quality = []
        for d in self.rules:
            q = {"rule": d["text"], "relation": d["concl"], "precision": round(measure(d, stated, self.facts), 4)}
            if "stated_agreement" in d:
                q["stated_agreement"] = d["stated_agreement"]
            quality.append(q)
        key = {
            "structure": self.structure,
            "seed": self.seed,
            "params": self.params,
            "relations": list(self.rels),
            "truth": truth,
            "hidden": hidden,
            "undeterminable": undet,
            "corrupted": sorted(self.corrupted),
            "unseen": unseen,
            "rules": [d["text"] for d in self.rules if d["generating"]],
            "conditions": self.conditions,
            "rule_quality": quality,
        }
        meta = {"rules": self.rules, "single": sorted(self.single), "checks": self.checks}
        return lines, key, meta


# ---------------------------------------------------------------------------
# rule application (used for rule_quality and by check())

def index(facts):
    idx = {}
    for r, s, o in facts:
        idx.setdefault(r, {}).setdefault(s, []).append(o)
    return idx


def predict(rule, stated):
    """Set of (rel, s, o) the rule concludes in one step from the stated facts."""
    idx = index(stated)
    out = set()
    k = rule["kind"]
    if k == "compose":
        A, B, C = idx.get(rule["a"], {}), idx.get(rule["b"], {}), rule["concl"]
        cond = rule.get("cond")
        for x, ys in A.items():
            if cond:
                cats = idx.get(cond[0], {}).get(x, [])
                if not any(c in cond[1] for c in cats):
                    continue
            for y in ys:
                for z in B.get(y, []):
                    out.add((C, x, z))
    elif k == "trans":
        R = idx.get(rule["concl"], {})
        for a, bs in R.items():
            for b in bs:
                for c in R.get(b, []):
                    if c != a:
                        out.add((rule["concl"], a, c))
    elif k == "reverse":
        P = idx.get(rule["p"], {})
        for a, bs in P.items():
            for b in bs:
                out.add((rule["concl"], b, a))
    else:
        raise ValueError(k)
    return out


def closure(rule, stated):
    """Everything derivable from the stated facts by repeated application of the rule."""
    if rule["kind"] != "trans":
        return predict(rule, stated)
    R = rule["concl"]
    up = {}
    for r, s, o in stated:
        if r == R:
            up.setdefault(s, set()).add(o)
    out = set()
    for a in list(up):
        seen, stack = set(), list(up[a])
        while stack:
            b = stack.pop()
            if b in seen or b == a:
                continue
            seen.add(b)
            stack.extend(up.get(b, ()))
        for b in seen:
            out.add((R, a, b))
    return out - set(stated)


def measure(rule, stated, truth):
    """Precision over the facts the rule fires on (premises stated), judged against truth."""
    pred = predict(rule, stated)
    if not pred:
        return 0.0
    return sum(1 for p in pred if p in truth) / len(pred)


# ---------------------------------------------------------------------------
# building blocks

def tree(w, roots, branch):
    """Levels of a hierarchy: levels[0] roots; parent map child -> parent."""
    levels = [w.names(roots)]
    parent = {}
    for b in branch:
        nxt = []
        for p in levels[-1]:
            kids = w.names(b)
            for c in kids:
                parent[c] = p
            nxt.extend(kids)
        levels.append(nxt)
    return levels, parent


def ancestors(x, parent):
    out = []
    while x in parent:
        x = parent[x]
        out.append(x)
    return out


def middle(w, ny, zs):
    """Ys and a one-valued B: Y -> Z covering every Z (needs ny >= len(zs))."""
    ys = w.names(ny)
    B = {}
    for i, y in enumerate(ys):
        B[y] = zs[i] if i < len(zs) else w.rng.choice(zs)
    return ys, B


# ---------------------------------------------------------------------------
# structures

DEFAULTS = {
    "reversed_weak": dict(roots=10, branch=[6, 10], stated=0.7, reverse_share=0.2),
    "graded": dict(n_x=200, n_y=40, n_z=20, stated=0.7, noise=[0, 0.05, 0.15, 0.30, 0.50]),
    "skewed": dict(n_x=1200, n_y=60, n_z=25, zipf=1.2, stated_high=0.9, stated_low=0.2),
    "multivalue": dict(n_x=600, n_y=80, n_z=40, values=[1, 5], stated=0.6),
    "exceptions": dict(n_x=1000, n_y=50, n_z=25, stated=0.7, exception_share=0.12, exception_stated=0.7),
    "competing": dict(n_x=800, n_z=25, y_per_z=2, p_good=0.9, p_bad=0.55, stated=0.6),
    "sparse": dict(examples=[6, 12, 30], stated=0.7, padding=1500, padding_entities=300),
    "conditional_rare": dict(n_x=600, n_y=40, n_z=20, categories=12, qualifying=1, attr_values=12, stated=0.85),
    "chain_noise": dict(roots=6, branch=[4, 5, 6], noise=0.1, stated=0.5),
    "control_degree": dict(n=500, links=700, zipf=1.0, relations=3),
}


def s_reversed_weak(w, p):
    levels, parent = tree(w, p["roots"], p["branch"])
    req = w.rel("requires", single=False)
    sug = w.rel("suggests", single=False)
    direct = [(c, parent[c]) for lvl in levels[1:] for c in lvl]
    for c, par in direct:
        w.add(req, c, par, "S")
    indirect = [(c, a) for lvl in levels[2:] for c in lvl for a in ancestors(c, parent)[1:]]
    keep = w.pick_stated(indirect, p["stated"])
    for i, (c, a) in enumerate(indirect):
        w.add(req, c, a, "S" if i in keep else "H")
    truth_req = set((c, a) for c, a in direct) | set(indirect)
    nodes = [x for lvl in levels for x in lvl]
    n = len(direct)
    k = int(round(p["reverse_share"] * n))
    order = list(range(len(direct)))
    w.rng.shuffle(order)
    pairs = []
    for i in order[:k]:
        c, par = direct[i]
        pairs.append((par, c))                     # suggests(a, b) with requires(b, a)
    taken = set(pairs)
    while len(pairs) < n:
        a, b = w.rng.choice(nodes), w.rng.choice(nodes)
        if a == b or (a, b) in taken or (b, a) in truth_req:
            continue
        taken.add((a, b))
        pairs.append((a, b))
    for a, b in pairs:
        w.add(sug, a, b, "S")
    w.rule("%s is transitive: X %s Y and Y %s Z gives X %s Z" % (req, req, req, req), "trans", concl=req)
    w.rule("decoy: X %s Y gives Y %s X" % (sug, req), "reverse", generating=False, p=sug, concl=req)
    w.checks.append(("rule_quality decoy = reverse_share", ("rq", 1), p["reverse_share"], 0.03))
    w.checks.append(("rule_quality transitivity = 1", ("rq", 0), 1.0, 0.0))


def compose_block(w, nx, ny, nz):
    a, b, c = w.rel(), w.rel(), w.rel()
    xs, zs = w.names(nx), w.names(nz)
    ys, B = middle(w, ny, zs)
    A = {x: w.rng.choice(ys) for x in xs}
    for y in ys:
        w.add(b, y, B[y], "S")
    for x in xs:
        w.add(a, x, A[x], "S")
    return a, b, c, xs, ys, zs, A, B


def s_graded(w, p):
    for i, noise in enumerate(p["noise"]):
        a, b, c, xs, ys, zs, A, B = compose_block(w, p["n_x"], p["n_y"], p["n_z"])
        keep = w.pick_stated(xs, p["stated"])
        stated = [x for j, x in enumerate(xs) if j in keep]
        nbad = int(round(noise * len(stated)))
        bad = set(w.rng.sample(stated, nbad))
        for j, x in enumerate(xs):
            z = B[A[x]]
            if x in bad:
                wrong = w.rng.choice([q for q in zs if q != z])
                w.corrupt(c, x, wrong, z, "H")
            else:
                w.add(c, x, z, "S" if j in keep else "H")
        agree = round((len(stated) - nbad) / len(stated), 4) if stated else 1.0
        w.rule("rule %d: X %s Y and Y %s Z gives X %s Z" % (i + 1, a, b, c), "compose", a=a, b=b, concl=c,
               stated_agreement=agree)
        w.checks.append(("rule %d stated agreement = 1 - noise" % (i + 1), ("agree", i), 1 - noise, 0.03))
        w.checks.append(("rule %d precision = 1" % (i + 1), ("rq", i), 1.0, 0.0))


def s_skewed(w, p):
    a, b, c = w.rel(), w.rel(), w.rel()
    xs, zs = w.names(p["n_x"]), w.names(p["n_z"])
    ys, B = middle(w, p["n_y"], zs)
    weights = [1.0 / (i + 1) ** p["zipf"] for i in range(len(ys))]
    A = {}
    for i, x in enumerate(xs):
        A[x] = ys[i] if i < len(ys) else w.rng.choices(ys, weights)[0]
    deg = {y: 0 for y in ys}
    for x in xs:
        deg[A[x]] += 1
    med = statistics.median(deg.values())
    high = [x for x in xs if deg[A[x]] > med]
    low = [x for x in xs if deg[A[x]] <= med]
    kh, kl = w.pick_stated(high, p["stated_high"]), w.pick_stated(low, p["stated_low"])
    state = {}
    for j, x in enumerate(high):
        state[x] = "S" if j in kh else "H"
    for j, x in enumerate(low):
        state[x] = "S" if j in kl else "H"
    for y in ys:
        w.add(b, y, B[y], "S")
    for x in xs:
        w.add(a, x, A[x], "S")
        w.add(c, x, B[A[x]], state[x])
    w.rule("X %s Y and Y %s Z gives X %s Z" % (a, b, c), "compose", a=a, b=b, concl=c)
    w.checks.append(("precision = 1", ("rq", 0), 1.0, 0.0))
    w.checks.append(("stated share, high-degree Y", ("share", c, high), p["stated_high"], 0.03))
    w.checks.append(("stated share, low-degree Y", ("share", c, low), p["stated_low"], 0.03))


def s_multivalue(w, p):
    a, b = w.rel(), w.rel(single=False)
    c = w.rel("carries", single=False)
    xs, ys, zs = w.names(p["n_x"]), w.names(p["n_y"]), w.names(p["n_z"])
    lo, hi = p["values"]
    B = {y: w.rng.sample(zs, w.rng.randint(lo, hi)) for y in ys}
    A = {x: w.rng.choice(ys) for x in xs}
    for y in ys:
        for z in B[y]:
            w.add(b, y, z, "S")
    concl = [(x, z) for x in xs for z in B[A[x]]]
    keep = w.pick_stated(concl, p["stated"])
    for x in xs:
        w.add(a, x, A[x], "S")
    for i, (x, z) in enumerate(concl):
        w.add(c, x, z, "S" if i in keep else "H")
    w.rule("X %s Y and Y %s Z gives X %s Z (every Z of Y)" % (a, b, c), "compose", a=a, b=b, concl=c)
    w.checks.append(("precision = 1", ("rq", 0), 1.0, 0.0))


def s_exceptions(w, p):
    a, b, c, xs, ys, zs, A, B = compose_block(w, p["n_x"], p["n_y"], p["n_z"])
    exc = set(w.rng.sample(xs, int(round(p["exception_share"] * len(xs)))))
    normal = [x for x in xs if x not in exc]
    exl = [x for x in xs if x in exc]
    kn, ke = w.pick_stated(normal, p["stated"]), w.pick_stated(exl, p["exception_stated"])
    for j, x in enumerate(normal):
        w.add(c, x, B[A[x]], "S" if j in kn else "H")
    for j, x in enumerate(exl):
        z = w.rng.choice([q for q in zs if q != B[A[x]]])
        w.add(c, x, z, "S" if j in ke else "U")
    w.rule("X %s Y and Y %s Z gives X %s Z (except for some X)" % (a, b, c), "compose", a=a, b=b, concl=c)
    w.checks.append(("precision = 1 - exception_share", ("rq", 0), 1 - p["exception_share"], 0.03))


def s_competing(w, p):
    a1, b1, a2, b2 = w.rel(), w.rel(), w.rel(), w.rel()
    c = w.rel()
    xs, zs = w.names(p["n_x"]), w.names(p["n_z"])
    truth = {x: w.rng.choice(zs) for x in xs}
    right = {}
    for a, b, share in ((a1, b1, p["p_good"]), (a2, b2, p["p_bad"])):
        ys = w.names(p["y_per_z"] * len(zs))
        B = {y: zs[i % len(zs)] for i, y in enumerate(ys)}
        by_z = {}
        for y in ys:
            by_z.setdefault(B[y], []).append(y)
        good = set(w.rng.sample(xs, int(round(share * len(xs)))))
        for y in ys:
            w.add(b, y, B[y], "S")
        for x in xs:
            if x in good:
                y = w.rng.choice(by_z[truth[x]])
            else:
                y = w.rng.choice([q for q in ys if B[q] != truth[x]])
            w.add(a, x, y, "S")
        right[a] = good
    keep = w.pick_stated(xs, p["stated"])
    for j, x in enumerate(xs):
        if j in keep:
            st = "S"
        else:
            st = "H" if x in right[a1] else "U"
        w.add(c, x, truth[x], st)
    w.rule("rule 1: X %s Y and Y %s Z gives X %s Z" % (a1, b1, c), "compose", a=a1, b=b1, concl=c)
    w.rule("rule 2: X %s Y and Y %s Z gives X %s Z" % (a2, b2, c), "compose", a=a2, b=b2, concl=c,
           derives=False)
    w.checks.append(("rule 1 precision = p_good", ("rq", 0), p["p_good"], 0.03))
    w.checks.append(("rule 2 precision = p_bad", ("rq", 1), p["p_bad"], 0.03))


def s_sparse(w, p):
    for i, ex in enumerate(p["examples"]):
        nx = max(ex, int(round(ex / p["stated"])))
        nz = max(2, nx // 4)
        ny = max(nz, nx // 3)
        a, b, c, xs, ys, zs, A, B = compose_block(w, nx, ny, nz)
        order = list(range(nx))
        w.rng.shuffle(order)
        keep = set(order[:ex])
        for j, x in enumerate(xs):
            w.add(c, x, B[A[x]], "S" if j in keep else "H")
        w.rule("rule %d: X %s Y and Y %s Z gives X %s Z" % (i + 1, a, b, c), "compose", a=a, b=b, concl=c)
        w.checks.append(("rule %d precision = 1" % (i + 1), ("rq", i), 1.0, 0.0))
        w.checks.append(("rule %d stated examples" % (i + 1), ("count", c), ex, 0))
    pad = w.rel(single=False)
    ents = w.names(p["padding_entities"])
    taken = set()
    while len(taken) < p["padding"]:
        s, o = w.rng.choice(ents), w.rng.choice(ents)
        if s != o and (s, o) not in taken:
            taken.add((s, o))
            w.add(pad, s, o, "S")


def s_conditional_rare(w, p):
    cat, attr = w.rel(), w.rel()
    a, b, c = w.rel(), w.rel(), w.rel()
    xs, zs = w.names(p["n_x"]), w.names(p["n_z"])
    ys, B = middle(w, p["n_y"], zs)
    cats, vals = w.names(p["categories"]), w.names(p["attr_values"])
    qual = cats[:p["qualifying"]]
    order = list(xs)
    w.rng.shuffle(order)
    C = {x: cats[i % len(cats)] for i, x in enumerate(order)}      # balanced categories
    order = list(xs)
    w.rng.shuffle(order)
    V = {x: vals[i % len(vals)] for i, x in enumerate(order)}      # irrelevant attribute, balanced
    A = {x: w.rng.choice(ys) for x in xs}
    for y in ys:
        w.add(b, y, B[y], "S")
    for x in xs:
        w.add(cat, x, C[x], "S")
        w.add(attr, x, V[x], "S")
        w.add(a, x, A[x], "S")
    q = [x for x in xs if C[x] in qual]
    keep = w.pick_stated(q, p["stated"])
    for j, x in enumerate(q):
        w.add(c, x, B[A[x]], "S" if j in keep else "H")
    text = "X %s Q and X %s Y and Y %s Z gives X %s Z, for Q in %s" % (cat, a, b, c, ", ".join(qual))
    w.rule(text, "compose", a=a, b=b, concl=c, cond=[cat, qual])
    w.rule("decoy: X %s Y and Y %s Z gives X %s Z (no condition)" % (a, b, c), "compose", generating=False,
           a=a, b=b, concl=c)
    w.conditions.append({"rule": text, "relation": cat, "values": list(qual)})
    w.checks.append(("conditional rule precision = 1", ("rq", 0), 1.0, 0.0))
    w.checks.append(("decoy precision = qualifying/categories", ("rq", 1), p["qualifying"] / p["categories"], 0.03))


def s_chain_noise(w, p):
    levels, parent = tree(w, p["roots"], p["branch"])
    r = w.rel("is under", single=False)
    level_of = {x: i for i, lvl in enumerate(levels) for x in lvl}
    direct = [c for lvl in levels[1:] for c in lvl]
    bad = set(w.rng.sample(direct, int(round(p["noise"] * len(direct)))))
    indirect = [(c, a) for lvl in levels[2:] for c in lvl for a in ancestors(c, parent)[1:]]
    keep = w.pick_stated(indirect, p["stated"])
    # provisional states; hidden vs undeterminable is settled by closure below
    for c in direct:
        if c in bad:
            wrong = w.rng.choice([q for q in levels[level_of[c] - 1] if q != parent[c]])
            w.corrupt(r, c, wrong, parent[c], "U")
        else:
            w.add(r, c, parent[c], "S")
    for i, (c, a) in enumerate(indirect):
        w.add(r, c, a, "S" if i in keep else "U")
    rule = w.rule("%s is transitive: X %s Y and Y %s Z gives X %s Z" % (r, r, r, r), "trans", concl=r)
    derivable = closure(rule, w.stated_lines())
    for k, st in list(w.facts.items()):
        if st != "S":
            w.facts[k] = "H" if k in derivable else "U"


def s_control_degree(w, p):
    ents = w.names(p["n"])
    weights = [1.0 / (i + 1) ** p["zipf"] for i in range(len(ents))]
    order = list(ents)
    w.rng.shuffle(order)                       # rank is independent of name order
    for _ in range(p["relations"]):
        r = w.rel(single=False)
        taken = set()
        while len(taken) < p["links"]:
            s = w.rng.choices(order, weights)[0]
            o = w.rng.choices(order, weights)[0]
            if s != o and (s, o) not in taken:
                taken.add((s, o))
                w.add(r, s, o, "S")


STRUCTURES = {
    "reversed_weak": s_reversed_weak,
    "graded": s_graded,
    "skewed": s_skewed,
    "multivalue": s_multivalue,
    "exceptions": s_exceptions,
    "competing": s_competing,
    "sparse": s_sparse,
    "conditional_rare": s_conditional_rare,
    "chain_noise": s_chain_noise,
    "control_degree": s_control_degree,
}


def _build(structure, seed, **params):
    if structure not in STRUCTURES:
        raise ValueError("unknown structure %r (choose from %s)" % (structure, ", ".join(STRUCTURES)))
    unknown = set(params) - set(DEFAULTS[structure])
    if unknown:
        raise ValueError("unknown params for %s: %s" % (structure, ", ".join(sorted(unknown))))
    p = json.loads(json.dumps(DEFAULTS[structure]))
    p.update(params)
    w = World(structure, int(seed), p)
    STRUCTURES[structure](w, p)
    return w.finalize()


def world(structure, seed, **params):
    lines, key, _ = _build(structure, seed, **params)
    return lines, key


# ---------------------------------------------------------------------------
# self-check

def check(structure, seed, **params):
    lines, key, meta = _build(structure, seed, **params)
    errs = []

    def need(cond, msg):
        if not cond:
            errs.append(msg)

    need(list(key) == KEY_FIELDS, "key fields %s" % list(key))
    rels = key["relations"]
    need(len(set(rels)) == len(rels), "duplicate relation phrases")
    for r in rels:
        need(bool(REL_RE.match(r)), "bad relation phrase %r" % r)
    need(len(set(lines)) == len(lines), "duplicate lines")
    stated = []
    for ln in lines:
        t = ln.split(" ")
        if len(t) < 3:
            errs.append("short line %r" % ln)
            continue
        s, r, o = t[0], " ".join(t[1:-1]), t[-1]
        need(r in rels, "unknown relation in %r" % ln)
        need(bool(NAME_RE.match(s)) and bool(NAME_RE.match(o)), "bad name in %r" % ln)
        need(re.sub(r"[0-9]+$", "", s) not in BLOCKLIST and re.sub(r"[0-9]+$", "", o) not in BLOCKLIST,
             "blocklisted stem in %r" % ln)
        stated.append((r, s, o))
    stated_set = set(stated)
    truth = set(tuple(f) for f in key["truth"])
    hidden = set(tuple(f) for f in key["hidden"])
    single = set(meta["single"])
    corrupted = key["corrupted"]
    wrong_lines = set((r, s, wr) for r, s, wr, _ in corrupted)
    # every stated line is true or a listed corruption
    need(stated_set <= truth | wrong_lines, "stated line neither true nor corrupted")
    need(not (wrong_lines & truth), "corrupted wrong line is in truth")
    need(wrong_lines <= stated_set, "corrupted wrong line not stated")
    # one value per subject
    for r in single:
        subj = {}
        for (rr, s, o) in truth:
            if rr == r:
                subj[s] = subj.get(s, 0) + 1
        need(all(v == 1 for v in subj.values()), "one-valued relation %r has several values" % r)
    # states partition truth
    undet = set()
    for e in key["undeterminable"]:
        if len(e) == 2:
            need(e[0] in single, "two-field undeterminable for many-valued relation %r" % e[0])
            m = [f for f in truth if f[0] == e[0] and f[1] == e[1]]
            need(len(m) == 1, "undeterminable %r does not name one truth fact" % e)
            undet.update(m)
        else:
            need(tuple(e) in truth, "undeterminable %r not in truth" % e)
            undet.add(tuple(e))
    need(len(undet) == len(key["undeterminable"]), "duplicate undeterminable entries")
    st_true = stated_set & truth
    need(not (st_true & hidden) and not (st_true & undet) and not (hidden & undet), "states overlap")
    need(st_true | hidden | undet == truth, "states do not cover truth")
    need(hidden <= truth, "hidden not in truth")
    # corrupted right facts are true and unstated
    for r, s, wr, rt in corrupted:
        need((r, s, rt) in truth and (r, s, rt) not in stated_set, "corrupted right fact %r" % [r, s, rt])
        need((r, s, rt) in hidden or (r, s, rt) in undet, "corrupted right fact has no state")
    # hidden follows from facts through the generating rules; undeterminable does not
    derivable = set()
    for d in meta["rules"]:
        if d["generating"] and d.get("derives", True):
            derivable |= closure(d, stated)
    need(hidden <= derivable, "%d hidden facts not derivable" % len(hidden - derivable))
    need(not (undet & derivable), "%d undeterminable facts derivable" % len(undet & derivable))
    # unseen
    seen = set(s for _, s, _ in stated) | set(o for _, _, o in stated)
    ents = set(s for _, s, _ in truth) | set(o for _, _, o in truth)
    need(sorted(ents - seen) == key["unseen"], "unseen list wrong")
    need(key["unseen"] == [] or params, "unseen not empty at defaults")
    # rules, rule_quality, conditions
    need(len(key["rule_quality"]) == len(meta["rules"]), "rule_quality length")
    need(all(0.0 <= q["precision"] <= 1.0 for q in key["rule_quality"]), "precision out of range")
    for q, d in zip(key["rule_quality"], meta["rules"]):
        need(abs(q["precision"] - measure(d, stated, truth)) < 1e-3, "precision not measured on world")
        need(q["relation"] in rels, "rule_quality relation")
    need(bool(key["conditions"]) == (structure == "conditional_rare"), "conditions")
    if structure == "control_degree":
        need(not key["hidden"] and not key["undeterminable"], "control has hidden/undeterminable")
        need(truth == stated_set, "control truth != stated")
        need(not key["rules"] and not key["rule_quality"], "control has rules")
    else:
        need(bool(key["rules"]), "no rules")
    for label, what, expect, tol in meta["checks"]:
        if what[0] == "rq":
            got = key["rule_quality"][what[1]]["precision"]
        elif what[0] == "agree":
            got = key["rule_quality"][what[1]]["stated_agreement"]
        elif what[0] == "share":
            xs = set(what[2])
            tot = [f for f in truth if f[0] == what[1] and f[1] in xs]
            got = sum(1 for f in tot if f in stated_set) / len(tot) if tot else expect
        elif what[0] == "count":
            got = sum(1 for f in stated if f[0] == what[1])
        need(abs(got - expect) <= tol + 1e-9, "%s: %s vs %s" % (label, got, expect))
    if not params:
        need(1500 <= len(lines) <= 6000, "line count %d outside 1500..6000" % len(lines))
    # determinism
    l2, k2 = world(structure, seed, **params)
    need(l2 == lines and json.dumps(k2, sort_keys=True) == json.dumps(key, sort_keys=True), "not deterministic")
    return errs, len(lines)


def run_check():
    bad = 0
    for st in STRUCTURES:
        counts, before = [], bad
        for seed in range(3):
            errs, n = check(st, seed)
            counts.append(n)
            for e in errs:
                print("FAIL %s seed %d: %s" % (st, seed, e))
                bad += 1
        a, b = world(st, 0)[0], world(st, 1)[0]
        if a == b:
            print("FAIL %s: seeds 0 and 1 give the same world" % st)
            bad += 1
        print("%-17s ok=%s lines(seed 0,1,2)=%s" % (st, "no" if bad > before else "yes", counts))
    print("check: %s" % ("FAILED (%d)" % bad if bad else "all structures pass, seeds 0..2, deterministic"))
    return bad == 0


def main(argv):
    if argv[1:2] == ["--check"]:
        return 0 if run_check() else 1
    if len(argv) < 4:
        print(__doc__.strip())
        print("structures: " + ", ".join(STRUCTURES))
        return 2
    structure, seed, outdir = argv[1], int(argv[2]), argv[3]
    params = {}
    for kv in argv[4:]:
        k, _, v = kv.partition("=")
        params[k] = json.loads(v)
    lines, key = world(structure, seed, **params)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "facts.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(outdir, "key.json"), "w") as f:
        json.dump(key, f, indent=1)
    print("%s seed %d: %d lines -> %s" % (structure, seed, len(lines), outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
