"""E5-E7: Hunt Mode vs. counter-oriented models on a synthetic grammar with known structure.

Ground truth: a small probabilistic grammar. 30% of (ADJ, NOUN) pairs never appear in training.
We test: held-out bits/word on sentences that contain only unseen pairs (generalization),
category discovery purity (discovery), generation validity + novelty (memorization vs generalization),
and Hunt Mode's actual behaviour on the same data."""
import random, math, collections, json, itertools, lzma
from vtx import Vault

rng = random.Random(7)
LEX = {
    "NAME": "ana bo cyr dax eli fen gus hal ivo jun".split(),
    "VERB": "carries paints sells finds drops fixes".split(),
    "ADJ": "red blue old tiny heavy shiny broken green".split(),
    "NOUN": "lamp chair kettle drum rope vase clock mirror sled bowl".split(),
    "VINT": "rests waits sits glows hides".split(),
    "PREP": "in near under".split(),
    "PLACE": "barn kitchen garden cellar attic market shed harbor".split(),
}
TEMPLATES = [
    ["NAME", "VERB", "the", "ADJ", "NOUN", "PREP", "the", "PLACE", "."],
    ["the", "ADJ", "NOUN", "VINT", "PREP", "the", "PLACE", "."],
    ["NAME", "VINT", "PREP", "the", "PLACE", "."],
]
pairs = list(itertools.product(LEX["ADJ"], LEX["NOUN"])); rng.shuffle(pairs)
held = set(pairs[: int(0.3 * len(pairs))])
TRUE_CAT = {w: c for c, ws in LEX.items() for w in ws}

def sample(require_held=None):
    while True:
        t = rng.choice(TEMPLATES[:2] if require_held is not None else TEMPLATES)
        s = [rng.choice(LEX[x]) if x in LEX else x for x in t]
        if "ADJ" in t:
            i = t.index("ADJ"); p = (s[i], s[i + 1])
            if require_held is True and p not in held: continue
            if require_held is None and p in held: continue
        return s

train = [sample() for _ in range(3000)]
test = [sample(require_held=True) for _ in range(300)]
train_set = {" ".join(s) for s in train}

def grammatical(ws):
    for t in TEMPLATES:
        if len(t) == len(ws) and all((w == x) if x not in LEX else (TRUE_CAT.get(w) == x) for w, x in zip(ws, t)):
            return True
    return False

# ---------------- M1: word trigram counter model, Witten-Bell interpolation ----------------
class NGram:
    def __init__(s, n, seqs, vocab):
        s.n, s.V = n, vocab; s.c = [collections.Counter() for _ in range(n + 1)]; s.ctx = [collections.Counter() for _ in range(n + 1)]
        s.types = [collections.defaultdict(set) for _ in range(n + 1)]
        for q in seqs:
            q = ["<s>"] * (n - 1) + q
            for i in range(n - 1, len(q)):
                for k in range(1, n + 1):
                    h = tuple(q[i - k + 1:i]); s.c[k][h + (q[i],)] += 1; s.ctx[k][h] += 1; s.types[k][h].add(q[i])
    def p(s, w, hist):
        pr = 1.0 / len(s.V)
        for k in range(1, s.n + 1):
            h = tuple(hist[len(hist) - (k - 1):]) if k > 1 else ()
            tot = s.ctx[k][h]
            if tot == 0: continue
            t = len(s.types[k][h]); lam = tot / (tot + t)
            pr = lam * s.c[k][h + (w,)] / tot + (1 - lam) * pr
        return pr
    def bits(s, seqs):
        b = n = 0
        for q in seqs:
            h = ["<s>"] * (s.n - 1)
            for w in q: b -= math.log2(s.p(w, h)); h.append(w); n += 1
        return b / n
    def gen(s, r, maxlen=12):
        h = ["<s>"] * (s.n - 1); out = []
        for _ in range(maxlen):
            ws = list(s.V); ps = [s.p(w, h) for w in ws]
            w = r.choices(ws, ps)[0]; out.append(w); h.append(w)
            if w == ".": break
        return out

vocab = sorted({w for s in train for w in s})
m1 = NGram(3, train, vocab)

# ---------------- M2: discovered word classes (counter-based distributional clustering) ----------------
def discover_classes(seqs, thresh=0.5):
    L = collections.defaultdict(collections.Counter); Rr = collections.defaultdict(collections.Counter)
    for q in seqs:
        q = ["<s>"] + q + ["</s>"]
        for i in range(1, len(q) - 1): L[q[i]][q[i - 1]] += 1; Rr[q[i]][q[i + 1]] += 1
    cls = {w: w for w in L}
    def sig(w):  # context signature at the CURRENT class level -> recursion lifts the representation a layer
        l = collections.Counter({cls.get(k, k): 0 for k in L[w]}); r = collections.Counter()
        for k, v in L[w].items(): l[cls.get(k, k)] += v
        for k, v in Rr[w].items(): r[cls.get(k, k)] += v
        return l, r
    def cos(a, b):
        num = sum(a[k] * b[k] for k in a); da = math.sqrt(sum(x * x for x in a.values())); db = math.sqrt(sum(x * x for x in b.values()))
        return num / (da * db) if da and db else 0
    for _round in range(4):
        members = collections.defaultdict(list)
        for w, c in cls.items(): members[c].append(w)
        csig = {}
        for c, ws in members.items():
            l = collections.Counter(); r = collections.Counter()
            for w in ws: a, b = sig(w); l.update(a); r.update(b)
            csig[c] = (l, r)
        cs = list(csig); merged = False
        for a, b in sorted(((a, b) for a in cs for b in cs if a < b),
                           key=lambda ab: -min(cos(csig[ab[0]][0], csig[ab[1]][0]), cos(csig[ab[0]][1], csig[ab[1]][1]))):
            sim = min(cos(csig[a][0], csig[b][0]), cos(csig[a][1], csig[b][1]))
            if sim < thresh: break
            ra, rb = cls_root(cls, a), cls_root(cls, b)
            if ra != rb:
                for w in cls:
                    if cls[w] == rb: cls[w] = ra
                merged = True
        if not merged: break
    return cls
def cls_root(cls, c): return c

cls = discover_classes(train)
groups = collections.defaultdict(set)
for w, c in cls.items(): groups[c].add(w)
# purity: for each discovered group, fraction of members sharing the majority true category
open_words = [w for w in cls if w in TRUE_CAT]
purity = sum(max(collections.Counter(TRUE_CAT.get(w, w) for w in g).values()) for g in groups.values()) / len(cls)
# completeness: for each true category, fraction of its words in its largest discovered group
compl = {c: max(len(set(ws) & g) for g in groups.values()) / len(ws) for c, ws in LEX.items()}

class ClassModel:
    def __init__(s, seqs, cls):
        s.cls = cls; s.cn = NGram(3, [[cls[w] for w in q] for q in seqs], sorted(set(cls.values())))
        s.emit = collections.defaultdict(collections.Counter)
        for q in seqs:
            for w in q: s.emit[cls[w]][w] += 1
    def p(s, w, hist):
        c = s.cls.get(w)
        if c is None: return 1e-6
        e = s.emit[c]; return s.cn.p(c, [s.cls.get(x, x) for x in hist]) * e[w] / sum(e.values())
    def bits(s, seqs):
        b = n = 0
        for q in seqs:
            h = ["<s>"] * 2
            for w in q: b -= math.log2(s.p(w, h)); h.append(w); n += 1
        return b / n
    def gen(s, r, maxlen=12):
        h = ["<s>"] * 2; out = []
        for _ in range(maxlen):
            cs = s.cn.V; ps = [s.cn.p(c, h) for c in cs]; c = r.choices(cs, ps)[0]; h.append(c)
            e = s.emit[c]; w = r.choices(list(e), list(e.values()))[0]; out.append(w)
            if w == ".": break
        return out

m2 = ClassModel(train, cls)

class Mix:
    def __init__(s, a, b, lam): s.a, s.b, s.l = a, b, lam
    def bits(s, seqs):
        bt = n = 0
        for q in seqs:
            h = ["<s>"] * 2
            for w in q: bt -= math.log2(s.l * s.a.p(w, h) + (1 - s.l) * s.b.p(w, h)); h.append(w); n += 1
        return bt / n

R = {"train_sentences": len(train), "test_sentences_all_unseen_pairs": len(test), "vocab": len(vocab),
     "uniform_bits_per_word": round(math.log2(len(vocab)), 3)}
test_seen = [sample() for _ in range(300)]
R["M1_word_trigram"] = {"bits_seen_combos": round(m1.bits(test_seen), 3), "bits_unseen_combos": round(m1.bits(test), 3)}
R["M2_discovered_class_trigram"] = {"bits_seen_combos": round(m2.bits(test_seen), 3), "bits_unseen_combos": round(m2.bits(test), 3),
                                    "n_classes": len(groups), "purity": round(purity, 3),
                                    "completeness": {k: round(v, 2) for k, v in compl.items()}}
R["M3_mix_0.5"] = {"bits_seen_combos": round(Mix(m1, m2, .5).bits(test_seen), 3), "bits_unseen_combos": round(Mix(m1, m2, .5).bits(test), 3)}

# focus: the bits spent on the NOUN right after an unseen ADJ
def noun_bits(model):
    b = []
    for q in test:
        i = q.index(next(w for w in q if TRUE_CAT.get(w) == "NOUN"))
        h = ["<s>"] * 2 + q[:i]; b.append(-math.log2(model.p(q[i], h)))
    return round(sum(b) / len(b), 3)
R["noun_after_unseen_adj_bits"] = {"ideal": round(math.log2(len(LEX["NOUN"])), 3), "M1": noun_bits(m1), "M2": noun_bits(m2)}

# generation validity / novelty
def gen_stats(model, n=400):
    r = random.Random(3); g = [model.gen(r) for _ in range(n)]
    valid = [s for s in g if grammatical(s)]
    novel = [s for s in valid if " ".join(s) not in train_set]
    novel_pair = [s for s in valid if "the" in s and len(s) > 3 and any((s[i], s[i + 1]) in held for i in range(len(s) - 1))]
    return {"valid": round(len(valid) / n, 3), "valid_and_novel": round(len(novel) / n, 3),
            "uses_heldout_pair": round(len(novel_pair) / n, 3)}
R["gen_M1"] = gen_stats(m1); R["gen_M2"] = gen_stats(m2)

# ---------------- Voltex on the same corpus ----------------
v = Vault()
for s in train:
    r = v.ingest(" ".join(s)); r.pinned = True
raw = "\n".join(" ".join(s) for s in train).encode()
R["voltex_on_train"] = {"raw_bytes": len(raw), "vtxe_bytes": v.size_bytes(), "xz_bytes": len(lzma.compress(raw, preset=9)),
                        "nodes": len(v.m)}
# Hunt: seed at a random atom, 20 steps, exactly as runNeuralHunt
hr = random.Random(5); outs = []; jumps = steps = 0
atoms = [n for n in v.order if not n.chunk]
for _ in range(200):
    seed = hr.choice(atoms).id; txt, tr = v.hunt(seed, 20, hr); outs.append(txt)
    jumps += tr.count("JUMP"); steps += len(tr)
words = [w for o in outs for w in o.split()]
R["hunt"] = {"jump_fraction": round(jumps / steps, 3),
             "emitted_tokens_that_are_vocab_words": round(sum(w in vocab for w in words) / max(1, len(words)), 3),
             "grammatical_sentence_fragments": sum(grammatical(seg.split() + ["."]) for o in outs for seg in o.split(".") if seg.strip()),
             "examples": outs[:4]}
# Hunt implicit transition table: how many (left->right) edges exist per atom?
deg = collections.Counter(n.a for n in v.m.values() if n.chunk)
R["hunt"]["mean_outgoing_edges_per_node_with_any"] = round(sum(deg.values()) / len(deg), 2)
R["hunt"]["fraction_atoms_with_no_outgoing_edge"] = round(sum(1 for a in atoms if deg[a.id] == 0) / len(atoms), 3)

json.dump(R, open("results_e5_e7.json", "w"), indent=1)
print(json.dumps(R, indent=1))
print({c: sorted(g) for c, g in groups.items()})
