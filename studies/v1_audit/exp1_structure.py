"""E1-E4: what the existing Voltex actually does (structure, sharing, compression, decay)."""
import random, zlib, lzma, bz2, math, collections, json, sys
from vtx import Vault, sha

R = {}

# ---------- E1: does vault state ever influence the split for strings > 8 chars? ----------
corpus_lines = [l.rstrip("\n") for f in ["GPL-3", "Apache-2.0", "GFDL-1.3"]
                for l in open(f"/usr/share/common-licenses/{f}", encoding="utf-8", errors="ignore")
                if 8 < len(l.strip()) < 200]
v = Vault(); hits = 0; checks = 0
for line in corpus_lines[:400]:
    t = line
    # Count how often a prefix/suffix of length > 4 is found in the map (it never can be: chunk ids are hash(child ids))
    for i in range(2, len(t) - 2):
        if i > 4 or len(t) - i > 4:
            checks += 1
            if sha(t[:i].encode()) in v.m and sha(t[i:].encode()) in v.m: hits += 1
    v.ingest(t)
R["E1_split_lookups_longer_than_4"] = checks
R["E1_successful_lookups"] = hits

# Same corpus, fresh vault vs. warmed vault: identical trees?
def shape(vault, s):
    return vault.leaves(vault.ingest(s), [])
fresh = Vault(); warm = Vault()
for l in corpus_lines[400:800]: warm.ingest(l)
diff = sum(shape(fresh, l) != shape(warm, l) for l in corpus_lines[:400])
R["E1_trees_differing_fresh_vs_warm"] = diff

# ---------- E2: what kind of sharing does the parse permit? ----------
def chunk_overlap(s1, s2):
    vv = Vault(); r1 = vv.ingest(s1)
    ids1 = set(vv.m); r2 = vv.ingest(s2)
    def sub(n, acc):
        if n is None: return acc
        acc.add(n.id)
        if n.chunk: sub(vv.m.get(n.a), acc); sub(vv.m.get(n.b), acc)
        return acc
    c2 = {i for i in sub(r2, set()) if vv.m[i].chunk}
    return len(c2 & ids1), len(c2)
base = "XQ7Z" * 6   # 24 chars, no spaces
R["E2_shared_suffix_nospace"] = chunk_overlap("AAAAAA" + base, "BBBBBB" + base)
R["E2_shared_suffix_offset_by_1"] = chunk_overlap("AAAAAA" + base, "BBBBB" + base)
R["E2_shared_prefix_nospace"] = chunk_overlap(base + "AAAAAA", base + "BBBBBB")
R["E2_shared_middle_words"] = chunk_overlap("alpha the shared middle phrase omega", "gamma the shared middle phrase delta")

# ---------- E3: compression on the EVO JSON workload and on natural text ----------
def dummy_json(i, rng):
    eye = ["blue", "brown", "green", "amber", "gray"]; fr = ["apple", "banana", "strawberry", "mango", "kiwi"]
    dp = ["NEURAL_BIO", "CYBER_LOGIC", "QUANTUM_OPS", "VOLTEX_LABS"]
    return ('{"_id":"5f%06x%06x","index":%d,"isActive":%s,"balance":"$%.2f","age":%d,"eyeColor":"%s",'
            '"name":"Agent_%d","company":"%s","location":[%.4f,%.4f],"favoriteFruit":"%s"}') % (
        rng.randrange(0xFFFFFF), rng.randrange(0xFFFFFF), i, "true" if rng.random() < .5 else "false",
        1000 + rng.randrange(500000) / 100, 18 + rng.randrange(50), rng.choice(eye), i, rng.choice(dp),
        rng.randrange(1800000) / 10000 - 90, rng.randrange(3600000) / 10000 - 180, rng.choice(fr))

def repair_grammar_bytes(seqs):
    """Re-Pair (Larsson & Moffat 1999): repeatedly replace the most frequent adjacent pair with a new symbol.
    Returns (approx encoded bytes, number of rules, final sequence length). Cost model: 2 symbols/rule +
    final sequence, entropy-coded at log2(alphabet) bits/symbol -- a crude but fair grammar-size estimate."""
    seqs = [list(s.encode()) for s in seqs]; nxt = 256; rules = 0
    while True:
        cnt = collections.Counter()
        for s in seqs:
            for i in range(len(s) - 1): cnt[(s[i], s[i + 1])] += 1
        if not cnt: break
        pair, c = cnt.most_common(1)[0]
        if c < 2: break
        for k, s in enumerate(seqs):
            out = []; i = 0
            while i < len(s):
                if i < len(s) - 1 and (s[i], s[i + 1]) == pair: out.append(nxt); i += 2
                else: out.append(s[i]); i += 1
            seqs[k] = out
        nxt += 1; rules += 1
    final = sum(len(s) for s in seqs)
    bits = (2 * rules + final) * math.log2(max(nxt, 2))
    return int(bits / 8), rules, final

def compress_report(name, lines, repair=True):
    raw = "\n".join(lines).encode()
    vv = Vault()
    for l in lines:
        r = vv.ingest(l); r.pinned = True
    atoms = sum(not n.chunk for n in vv.m.values()); chunks = len(vv.m) - atoms
    out = {"raw_bytes": len(raw), "voltex_vtxe_bytes": vv.size_bytes(), "voltex_nodes": len(vv.m),
           "voltex_atoms": atoms, "voltex_chunks": chunks,
           "nodes_per_line": round(len(vv.m) / len(lines), 1),
           "zlib9": len(zlib.compress(raw, 9)), "bz2": len(bz2.compress(raw)), "xz": len(lzma.compress(raw, preset=9))}
    # How many chunk nodes are referenced by >1 parent? (true cross-record sharing)
    out["chunks_with_multiple_parents"] = sum(1 for n in vv.m.values() if n.chunk and len(n.dend) > 1)
    if repair:
        b, rules, final = repair_grammar_bytes(lines); out.update(repair_bytes=b, repair_rules=rules)
    R["E3_" + name] = out
    return vv

rng = random.Random(1)
evo = [dummy_json(i, rng) for i in range(1, 1001)]
vv_evo = compress_report("evo_json_1000", evo)
compress_report("license_text_lines", corpus_lines[:1500])

# ---------- E4: does a pinned root survive 40 DREAM cycles intact? ----------
vd = Vault(); root = vd.ingest("critical configuration v2.1"); root.pinned = True; root.vit = 1.0
before = vd.unroll(root)
for _ in range(40): vd.dream()
after = vd.unroll(vd.m.get(root.id)) if root.id in vd.m else None
R["E4_pinned_before"] = before; R["E4_pinned_after_40_dreams"] = after
R["E4_nodes_left"] = len(vd.m)

json.dump(R, open("results_e1_e4.json", "w"), indent=1, default=str)
print(json.dumps(R, indent=1, default=str))
