"""Turing machines for the harness study: programs, a plain simulator (ground truth), and step facts.

A machine is a transition table {(state, symbol): (write, move, next)}. The engine never sees the table. It sees
example steps as facts, one entity per step with three output slots:

    s has state <q>        s reads <symbol>
    w is write of s        w has symbol <symbol>          (round 1: w has value <symbol>)
    m is move of s         m has direction left|right     (round 1: m has value ...)
    n is next of s         n has state <state>|halt       (round 1: n has value ...)

The output slots are shaped like a gate's output wire (studies/trees, studies/compute), so a tree rule rooted at the
step can decide each one from the step's state and symbol.
"""
import os, random

# Round 1 put every output in one relation, `has value`: 10 distinct values, above the tree search's limit of 8 for
# a target (DEVIATIONS.md 1). Round 2 (ROUND=2, the default) uses one relation per kind of value.
ROUND = os.environ.get("ROUND", "2")
REL = ({"write": "has value", "move": "has value", "next": "has value"} if ROUND == "1" else
       {"write": "has symbol", "move": "has direction", "next": "has state"})

PROGRAMS = {
    # 3-state, 2-symbol busy beaver (Lin and Rado): halts after 14 steps with six ones on the tape
    "bb3": {("A", "zero"): ("one", "right", "B"), ("A", "one"): ("one", "right", "halt"),
            ("B", "zero"): ("zero", "right", "C"), ("B", "one"): ("one", "right", "B"),
            ("C", "zero"): ("one", "left", "C"), ("C", "one"): ("one", "left", "A")},
    # binary increment, head on the rightmost bit: carry through ones, then write one and stop
    "inc": {("carry", "one"): ("zero", "left", "carry"), ("carry", "zero"): ("one", "left", "halt"),
            ("carry", "blank"): ("one", "left", "halt")},
}
BLANK = {"bb3": "zero", "inc": "blank"}
START = {"bb3": "A", "inc": "carry"}


def simulate(prog, tape, head, state, max_steps=10_000):
    """Ground truth. tape: dict position -> symbol. Returns (tape, head, state, steps)."""
    table, blank = PROGRAMS[prog], BLANK[prog]
    tape = dict(tape); steps = 0
    while state != "halt" and steps < max_steps:
        w, m, n = table[(state, tape.get(head, blank))]
        tape[head] = w; head += 1 if m == "right" else -1; state = n; steps += 1
    return tape, head, state, steps


class Names:
    def __init__(self, seed):
        syl = [a + b for a in "bdfgklmnprstvz" for b in "aeiou"]
        pool = [x + y + z for x in syl for y in syl for z in syl]; random.Random(seed).shuffle(pool); self.it = iter(pool)

    def __call__(self): return next(self.it)


def step_facts(names, state, symbol, outputs=None):
    """Facts for one step entity. outputs = (write, move, next) to state them (an example); None to leave them open.
    Returns (lines, slots) where slots = {"write": w, "move": m, "next": n}."""
    s, w, m, n = names(), names(), names(), names()
    lines = [f"{s} has state {state}", f"{s} reads {symbol}", f"{w} is write of {s}", f"{m} is move of {s}", f"{n} is next of {s}"]
    if outputs:
        lines += [f"{w} {REL['write']} {outputs[0]}", f"{m} {REL['move']} {outputs[1]}", f"{n} {REL['next']} {outputs[2]}"]
    return lines, {"write": w, "move": m, "next": n}


def examples(prog, per_transition, names, rng, skip=()):
    """per_transition example steps for every transition except those in skip, shuffled."""
    out = []
    for key, val in PROGRAMS[prog].items():
        if key in skip: continue
        for _ in range(per_transition):
            out += step_facts(names, key[0], key[1], val)[0]
    rng.shuffle(out); return out
