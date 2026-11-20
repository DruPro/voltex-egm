"""Faithful Python port of voltex_paged.cpp core (ingest / split / unroll / dream / hunt).
Used only for measurement; validated against the compiled C++ binary (same root IDs, same counts)."""
import hashlib, math, random

DECAY, THRESH = 0.95, 0.2

class Node:
    __slots__ = ("id", "a", "b", "lex", "vit", "chunk", "pinned", "dend")
    def __init__(s, id, chunk, a=None, b=None, lex=None):
        s.id, s.chunk, s.a, s.b, s.lex = id, chunk, a, b, lex
        s.vit, s.pinned, s.dend = 1.0, False, []

def sha(b): return hashlib.sha256(b).digest()

class Vault:
    def __init__(s):
        s.m = {}        # id -> Node
        s.order = []    # creation order (C++ list head = newest)
    # --- findNeuralSplit, line 429 ---
    def split(s, t):
        n = len(t)
        if n <= 4: return n // 2
        weakest, mn = n // 2, 2.0
        for i in range(2, n - 2):
            a = s.m.get(sha(t[:i].encode())); b = s.m.get(sha(t[i:].encode()))
            st = math.sqrt(a.vit * b.vit) if (a and b) else 0.5
            if t[i] == ' ': st -= 0.2
            if st < mn: mn, weakest = st, i
        return weakest
    # --- ingest, line 454 ---
    def ingest(s, t):
        if len(t) <= 4:
            id = sha(t.encode())
            e = s.m.get(id)
            if e: e.vit = 1.0; return e
            n = Node(id, False, lex=t); s.m[id] = n; s.order.append(n); return n
        k = s.split(t)
        a = s.ingest(t[:k]); b = s.ingest(t[k:])
        cid = sha(a.id + b.id)
        e = s.m.get(cid)
        if e: e.vit = min(e.vit + 0.1, 1.0); return e
        n = Node(cid, True, a.id, b.id); n.vit = math.sqrt(a.vit * b.vit)
        a.dend.append(cid); b.dend.append(cid)
        s.m[cid] = n; s.order.append(n); return n
    def unroll(s, n):
        if n is None: return "\x00"          # marks a missing (purged) child
        if not n.chunk: return n.lex
        return s.unroll(s.m.get(n.a)) + s.unroll(s.m.get(n.b))
    def depth(s, n):
        if n is None or not n.chunk: return 1
        return 1 + max(s.depth(s.m.get(n.a)), s.depth(s.m.get(n.b)))
    def leaves(s, n, out):
        if n is None: out.append("?"); return out
        if not n.chunk: out.append(n.lex); return out
        s.leaves(s.m.get(n.a), out); s.leaves(s.m.get(n.b), out); return out
    # --- executeDreamCycle, line 617 (morph is a no-op unless ids were rerouted) ---
    def dream(s):
        for n in s.order:
            if not n.pinned and n.vit > 0: n.vit *= DECAY
            if n.vit < THRESH or n.vit < 0:
                n.vit = -2.0 if (n.dend and n.vit >= 0) else -1.0
        keep = []
        for n in s.order:
            if n.vit <= -1.0: s.m.pop(n.id, None)
            else: keep.append(n)
        s.order = keep
    # --- runNeuralHunt, line 806 ---
    def hunt(s, seed, steps=20, rng=random):
        cur, out, trace = seed, [], []
        for _ in range(steps):
            m = s.m.get(cur)
            if m is None: break
            if not m.chunk: out.append(m.lex)
            cands = [s.m[n.b] for n in s.order if n.chunk and n.a == cur and n.b in s.m]
            if cands:
                cands.sort(key=lambda x: -x.vit); k = cands[:3]
                tot = sum(c.vit for c in k); pick = rng.random() * tot; acc = 0
                for c in k:
                    acc += c.vit
                    if acc >= pick: cur = c.id; break
                trace.append("step")
            else:
                newest = s.order[::-1]; d = rng.randrange(20)
                cur = newest[min(d, len(newest) - 1)].id; trace.append("JUMP")
        return "".join(out), trace
    def size_bytes(s):
        """On-disk-ish cost per the .vtxe export format (28 B node row + 32 B id + lexeme + 4 B per dendrite)."""
        tot = 24
        for n in s.m.values():
            tot += 32 + 28 + 4 * len(n.dend) + (len(n.lex) if n.lex else 0)
        return tot
