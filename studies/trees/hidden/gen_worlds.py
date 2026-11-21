"""Tree-rules worlds. G: 1,000 gates (xor, and, or, nand, decoy rnd); A: 600 example gates + 20 four-bit ripple-carry adders.
Writes obs/<world>_s<seed>.txt (all the engine sees) and hidden/<world>_s<seed>.json (truth)."""
import json, random, sys
OPS = {"xor": lambda a, b: a ^ b, "and": lambda a, b: a & b, "or": lambda a, b: a | b, "nand": lambda a, b: 1 - (a & b)}
WORD = {0: "zero", 1: "one"}

def namer(r):
    syl = [a + b for a in "bdfgklmnprstvz" for b in "aeiou"]
    pool = [x + y + z for x in syl for y in syl for z in syl[:12]]
    r.shuffle(pool); return iter(pool)

def gate(lines, names, kind, a, b, op_out, show_out, r):
    g, w1, w2, w3 = next(names), next(names), next(names), next(names)
    lines += [f"{w3} is output of {g}", f"{g} has first input {w1}", f"{g} has second input {w2}", f"{g} has kind {kind}",
              f"{w1} has value {WORD[a]}", f"{w2} has value {WORD[b]}"]
    if show_out: lines.append(f"{w3} has value {WORD[op_out]}")
    return w3

def world_g(seed):
    r = random.Random(seed); names = namer(r); lines = []; hidden = {}
    for kind in ["xor", "and", "or", "nand", "rnd"]:
        for i in range(200):
            a, b = r.randint(0, 1), r.randint(0, 1)
            out = r.randint(0, 1) if kind == "rnd" else OPS[kind](a, b)
            show = r.random() < 2 / 3
            w3 = gate(lines, names, kind, a, b, out, show, r)
            if not show: hidden[w3] = {"kind": kind, "value": WORD[out]}
    r.shuffle(lines); return lines, {"hidden_outputs": hidden}

def world_a(seed):
    r = random.Random(seed); names = namer(r); lines = []
    for kind in ["xor", "and", "or"]:
        for i in range(200):
            a, b = r.randint(0, 1), r.randint(0, 1); gate(lines, names, kind, a, b, OPS[kind](a, b), True, r)
    adders = []; wires = {}
    def g2(kind, w1, w2):   # a gate fed by existing wires; output hidden
        g, w3 = next(names), next(names)
        lines.extend([f"{w3} is output of {g}", f"{g} has first input {w1}", f"{g} has second input {w2}", f"{g} has kind {kind}"])
        wires[w3] = OPS[kind](wires[w1], wires[w2]); return w3
    for n in range(20):
        A, B = r.randint(0, 15), r.randint(0, 15)
        ins_a, ins_b = [], []
        for i in range(4):
            for bit, lst, val in ((i, ins_a, A), (i, ins_b, B)):
                w = next(names); wires[w] = (val >> bit) & 1; lines.append(f"{w} has value {WORD[wires[w]]}"); lst.append(w)
        s0 = g2("xor", ins_a[0], ins_b[0]); carry = g2("and", ins_a[0], ins_b[0]); outs = [s0]
        for i in range(1, 4):
            x1 = g2("xor", ins_a[i], ins_b[i]); s = g2("xor", x1, carry)
            c1 = g2("and", ins_a[i], ins_b[i]); c2 = g2("and", carry, x1); carry = g2("or", c1, c2); outs.append(s)
        outs.append(carry)
        adders.append({"a": A, "b": B, "sum": A + B, "outputs": outs})
    hidden = {w: WORD[v] for w, v in wires.items() if not any(f"{w} has value" in l for l in lines)}
    r.shuffle(lines); return lines, {"adders": adders, "hidden_wires": hidden, "wire_values": {w: WORD[v] for w, v in wires.items()}}

if __name__ == "__main__":
    for s in range(5):
        for name, fn in (("gates", world_g), ("adders", world_a)):
            lines, truth = fn(s)
            open(f"obs/{name}_s{s}.txt", "w").write("\n".join(lines) + "\n"); json.dump(truth, open(f"hidden/{name}_s{s}.json", "w"))
    g = json.load(open("hidden/gates_s0.json")); a = json.load(open("hidden/adders_s0.json"))
    print("gates s0: hidden outputs", len(g["hidden_outputs"]), "| adders s0: hidden wires", len(a["hidden_wires"]),
          "| sums check", all(sum((1 if a["wire_values"][w] == "one" else 0) << i for i, w in enumerate(x["outputs"])) == x["sum"] for x in a["adders"]))
