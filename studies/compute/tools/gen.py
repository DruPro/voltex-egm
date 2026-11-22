"""Worlds for the computation study: logic gates and unrolled cellular automata as facts, with complete truth.

  python3 gen.py      writes ../obs/<world>_s<seed>.txt and ../obs/<world>_s<seed>.truth.json

Fact format (the same as studies/trees): `w is output of g`, `g has first input w1` (second, third), `g has kind k`,
`w has value one|zero`. The engine never sees a truth table: it sees example gates (inputs and output stated) and
circuits whose primary inputs alone are stated. Truth comes from simulating the circuits in Python.

Worlds:
  nand      only NAND gates taught; circuits built from NANDs alone: XOR (4 NANDs), full adders (9), 4-bit adders (36)
  mixed     and, or, xor, not (one input) taught; 8-bit ripple-carry adders (carry chain ~17 gates deep), 2:1 multiplexers
  rule110   the Rule 110 cell update as one 3-input gate (left, centre, right) taught; held-out single gates, and an
            unrolled 16-cell x 16-step automaton (periodic edges) given only its first row
  rnd       control: a gate kind whose output is random, taught like the others; nothing about it should be confident
"""
import json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OBS = os.path.join(HERE, "..", "obs")
V = {0: "zero", 1: "one"}
OPS = {"nand": lambda a, b: 1 - (a & b), "and": lambda a, b: a & b, "or": lambda a, b: a | b,
       "xor": lambda a, b: a ^ b, "not": lambda a: 1 - a,
       "rule110": lambda l, c, r: {(1, 1, 1): 0, (1, 1, 0): 1, (1, 0, 1): 1, (1, 0, 0): 0,
                                   (0, 1, 1): 1, (0, 1, 0): 1, (0, 0, 1): 1, (0, 0, 0): 0}[(l, c, r)]}
SLOT = ["first", "second", "third"]


class World:
    def __init__(self, seed):
        self.r = random.Random(seed)
        syl = [a + b for a in "bdfgklmnprstvz" for b in "aeiou"]
        pool = [x + y + z for x in syl for y in syl for z in syl]; self.r.shuffle(pool); self.names = iter(pool)
        self.lines, self.value, self.hidden, self.depth, self.circuit = [], {}, set(), {}, {}

    def wire(self, v=None, stated=False, circuit=None):
        w = next(self.names)
        if v is not None:
            self.value[w] = v; self.depth[w] = 0
            if stated: self.lines.append(f"{w} has value {V[v]}")
        if circuit: self.circuit[w] = circuit
        return w

    def gate(self, kind, ins, show_out, circuit=None, rnd=False):
        g, out = next(self.names), next(self.names)
        self.lines += [f"{out} is output of {g}", f"{g} has kind {kind}"]
        self.lines += [f"{g} has {SLOT[i]} input {w}" for i, w in enumerate(ins)]
        v = self.r.randint(0, 1) if rnd else OPS[kind](*[self.value[w] for w in ins])
        self.value[out] = v; self.depth[out] = 1 + max(self.depth[w] for w in ins)
        if circuit: self.circuit[out] = circuit
        if show_out: self.lines.append(f"{out} has value {V[v]}")
        else: self.hidden.add(out)
        return out

    def examples(self, kind, n, arity, rnd=False, held=0):
        """n fully stated example gates (inputs and output), plus `held` with the output hidden (single-gate test)."""
        for i in range(n + held):
            ins = [self.wire(self.r.randint(0, 1), stated=True) for _ in range(arity)]
            self.gate(kind, ins, show_out=i < n, circuit=None if i < n else f"single_{kind}_{i}", rnd=rnd)

    def save(self, name):
        os.makedirs(OBS, exist_ok=True); self.r.shuffle(self.lines)
        open(os.path.join(OBS, name + ".txt"), "w").write("\n".join(self.lines) + "\n")
        truth = {w: V[self.value[w]] for w in self.hidden}
        json.dump({"hidden": truth, "depth": {w: self.depth[w] for w in self.hidden},
                   "circuit": {w: self.circuit.get(w) for w in self.hidden}},
                  open(os.path.join(OBS, name + ".truth.json"), "w"), indent=0)
        return len(self.lines), len(truth)


def nand_world(seed):
    W = World(1000 + seed); W.examples("nand", 400, 2)
    N = lambda a, b, c: W.gate("nand", [a, b], False, c)
    def xor(a, b, c):
        n1 = N(a, b, c); return N(N(a, n1, c), N(b, n1, c), c)
    def full_add(a, b, cin, c):
        n1 = N(a, b, c); s1 = N(N(a, n1, c), N(b, n1, c), c); n5 = N(s1, cin, c)
        return N(N(s1, n5, c), N(cin, n5, c), c), N(n5, n1, c)   # sum, carry
    bit = lambda: W.r.randint(0, 1)
    for k in range(30):
        c = f"xor_{k}"; xor(W.wire(bit(), True, c), W.wire(bit(), True, c), c)
    for k in range(30):
        c = f"fulladd_{k}"; full_add(W.wire(bit(), True, c), W.wire(bit(), True, c), W.wire(bit(), True, c), c)
    for k in range(20):
        c = f"add4_{k}"; carry = W.wire(0, True, c)
        for i in range(4): _, carry = full_add(W.wire(bit(), True, c), W.wire(bit(), True, c), carry, c)
    return W


def mixed_world(seed):
    W = World(2000 + seed)
    for k in ("and", "or", "xor"): W.examples(k, 200, 2)
    W.examples("not", 100, 1)
    G = lambda k, ins, c: W.gate(k, ins, False, c)
    bit = lambda: W.r.randint(0, 1)
    for k in range(10):
        c = f"add8_{k}"; carry = W.wire(0, True, c)
        for i in range(8):
            a, b = W.wire(bit(), True, c), W.wire(bit(), True, c)
            s1 = G("xor", [a, b], c); G("xor", [s1, carry], c)
            carry = G("or", [G("and", [a, b], c), G("and", [s1, carry], c)], c)
    for k in range(20):
        c = f"mux_{k}"; a, b, s = W.wire(bit(), True, c), W.wire(bit(), True, c), W.wire(bit(), True, c)
        G("or", [G("and", [a, G("not", [s], c)], c), G("and", [b, s], c)], c)
    return W


def rule110_world(seed, width=16, steps=16):
    W = World(3000 + seed); W.examples("rule110", 200, 3, held=60)
    row = [W.wire(W.r.randint(0, 1), True, "automaton") for _ in range(width)]
    for t in range(1, steps):
        row = [W.gate("rule110", [row[(i - 1) % width], row[i], row[(i + 1) % width]], False, "automaton")
               for i in range(width)]
    return W


def rnd_world(seed):
    W = World(4000 + seed)
    for k in ("and", "or"): W.examples(k, 200, 2)
    W.examples("rnd", 200, 2, rnd=True, held=60)
    return W


WORLDS = {"nand": nand_world, "mixed": mixed_world, "rule110": rule110_world, "rnd": rnd_world}

if __name__ == "__main__":
    for name, fn in WORLDS.items():
        for s in range(3):
            n, h = fn(s).save(f"{name}_s{s}")
            print(f"{name}_s{s}: {n} facts, {h} hidden wire values")
