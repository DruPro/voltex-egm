"""Mimic: a small programming language whose meaning is learned, not written.

You never define what an operation does. You show examples, and the Voltex EGM engine learns the rules from them;
every step a program takes is decided by a learned rule with a proof. When no learned rule decides a step, the
program stops and says so; it never guesses.

  python3 lang/mimic/mimic.py program.mim [--mode fresh|rebuild|observe] [--quiet]

Statements (one per line, `#` starts a comment):

  teach N                          examples per taught row (default 64; tree rules need many, docs/EVALUATION.md)

  function NAME                    a function, taught by rows of its table
    0 1 -> 1                       inputs -> output (values: letters or digits)
    ? 1 1 -> 0                     a row you know but don't teach: Mimic reports what the engine infers for it
  end

  machine NAME                     a Turing machine, taught by its transitions
    start STATE                    state the head starts in
    blank _                        the blank symbol (default _)
    carry 1 -> 0 left carry        STATE SYMBOL -> WRITE MOVE NEXT   (MOVE: left/right; NEXT may be halt)
  end

  circuit NAME a b -> s c          wire functions together (compiled once; each eval only snapshots new inputs)
    t = xor a b
    s = xor t c
  end

  run NAME on 1011 [at start|end|N] [max N] [trace]    run a machine on a tape (one character per symbol)
  eval NAME 1 0 [trace]            evaluate a circuit, or a function directly
  automaton NAME width W steps T start PATTERN         a row of W cells updated by a 3-input function NAME
  rules NAME                       show the rules the engine learned for NAME
  why NAME 1 0                     evaluate, then walk the proof of each output by asking for its premises in turn
  print text                       print text

Execution modes (--mode; all give the engine the same taught examples; measured in bench/RESULTS.md):
  fresh    (default) new entities for every step and every evaluation, ingested into the running engine
           (studies/harness). Correct on every bench program; about 11-13 ms per machine step.
  rebuild  a new engine for every step and evaluation, from the taught examples plus only the current state: no
           history and no leftover entities. Correct on every bench program; about 2x the cost of fresh.
  observe  a machine has one step entity, and each step restates its state and symbol as a snapshot
           (OBSERVE); circuits are compiled once and each eval snapshots new inputs. No new entities per step; the
           evidence layer keeps old states as history. The engine loses a record's current snapshot after 13-26
           restatements (repro_observe_loss.py), so long runs stop with UNKNOWN; never wrong, but not reliable. An output that is the same in every example can't be
learned (nothing shows what it depends on); Mimic applies it as declared by you and labels it so.
"""
import os, re, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import egm  # noqa: E402

SETTINGS = {"TREES": 1, "DEPTH": 0, "TENDENCYSTEPS": 0}
SLOTS = ["first", "second", "third"]
MAX_VALUES = 8   # the tree search's limit for a target relation (src/voltex2.cpp mineTrees; studies/harness)


class MimicError(Exception):
    pass


def tok(x):
    if not re.fullmatch(r"[A-Za-z0-9_]+", x): raise MimicError(f"not a valid value or name: {x!r} (letters, digits, _)")
    return x


# -------------------------------------------------------------------------------- parsing
class Program:
    def __init__(self):
        self.teach = 64; self.functions = {}; self.machines = {}; self.circuits = {}; self.actions = []

    @classmethod
    def parse(cls, text):
        p = cls(); lines = [(i + 1, l.split("#", 1)[0].strip()) for i, l in enumerate(text.splitlines())]
        lines = [(n, l) for n, l in lines if l]; k = 0
        def block(n0):
            nonlocal k; body = []
            while True:
                if k >= len(lines): raise MimicError(f"line {n0}: block without `end`")
                n, l = lines[k]; k += 1
                if l == "end": return body
                body.append((n, l))
        while k < len(lines):
            n, l = lines[k]; k += 1; w = l.split()
            try:
                if w[0] == "teach": p.teach = int(w[1])
                elif w[0] == "function": p.functions[tok(w[1])] = Function.parse(w[1], block(n))
                elif w[0] == "machine": p.machines[tok(w[1])] = Machine.parse(w[1], block(n))
                elif w[0] == "circuit": p.circuits[tok(w[1])] = Circuit.parse(l, block(n))
                elif w[0] in ("run", "eval", "automaton", "rules", "print", "why"): p.actions.append((n, w[0], l))
                else: raise MimicError(f"unknown statement {w[0]!r}")
            except MimicError as e:
                raise MimicError(f"line {n}: {e}") from None
            except (IndexError, ValueError):
                raise MimicError(f"line {n}: can't read {l!r}") from None
        return p


class Function:
    def __init__(self, name): self.name, self.rows, self.hidden, self.arity = name, {}, {}, None

    @classmethod
    def parse(cls, name, body):
        f = cls(name)
        for n, l in body:
            hide = l.startswith("?"); l = l.lstrip("? ").strip()
            if "->" not in l: raise MimicError(f"line {n}: a row looks like `0 1 -> 1`")
            ins, out = l.split("->"); ins = tuple(tok(x) for x in ins.split()); out = tok(out.strip())
            if f.arity is None: f.arity = len(ins)
            if len(ins) != f.arity: raise MimicError(f"line {n}: {name} takes {f.arity} inputs")
            if not 1 <= f.arity <= 3: raise MimicError(f"line {n}: functions take 1 to 3 inputs (tree rules join at most 4 branches)")
            (f.hidden if hide else f.rows)[ins] = out
        if not f.rows: raise MimicError(f"function {name} has no taught rows")
        return f

    def constant(self):
        outs = set(self.rows.values()); return outs.pop() if len(outs) == 1 else None


class Machine:
    def __init__(self, name): self.name, self.rows, self.hidden, self.start, self.blank = name, {}, {}, None, "_"

    @classmethod
    def parse(cls, name, body):
        m = cls(name)
        for n, l in body:
            w = l.split()
            if w[0] == "start": m.start = tok(w[1]); continue
            if w[0] == "blank": m.blank = tok(w[1]); continue
            hide = l.startswith("?"); w = l.lstrip("? ").split()
            if len(w) != 6 or w[2] != "->": raise MimicError(f"line {n}: a transition looks like `carry 1 -> 0 left carry`")
            mv = {"l": "left", "left": "left", "r": "right", "right": "right"}.get(w[4].lower())
            if not mv: raise MimicError(f"line {n}: move must be left or right")
            if len(w[1]) != 1 or len(w[3]) != 1: raise MimicError(f"line {n}: tape symbols are single characters")
            (m.hidden if hide else m.rows)[(tok(w[0]), tok(w[1]))] = (tok(w[3]), mv, tok(w[5]))
        if not m.start: raise MimicError(f"machine {name} needs `start STATE`")
        if not m.rows: raise MimicError(f"machine {name} has no taught transitions")
        return m

    def constant(self, i):
        outs = {v[i] for v in self.rows.values()}; return outs.pop() if len(outs) == 1 else None


class Circuit:
    def __init__(self, name, ins, outs): self.name, self.ins, self.outs, self.body = name, ins, outs, []

    @classmethod
    def parse(cls, head, body):
        w = head.split()
        if "->" not in w: raise MimicError("a circuit looks like `circuit NAME a b -> s c`")
        i = w.index("->"); c = cls(tok(w[1]), [tok(x) for x in w[2:i]], [tok(x) for x in w[i + 1:]])
        for n, l in body:
            m = re.fullmatch(r"(\w+)\s*=\s*(\w+)((?:\s+\w+)+)", l)
            if not m: raise MimicError(f"line {n}: a wire looks like `t = xor a b`")
            c.body.append((m.group(1), m.group(2), m.group(3).split(), n))
        return c


# -------------------------------------------------------------------------------- runtime
class Runtime:
    def __init__(self, prog, mode="fresh", out=print, binary=None, depth=0):
        if mode not in ("observe", "fresh", "rebuild"): raise MimicError(f"unknown mode {mode}")
        self.p, self.mode, self.fresh, self.out = prog, mode, mode == "fresh", out; self.n = 0; self.t = 0; self.timing = {}
        self.binary = binary or os.path.join(ROOT, "build", "voltex2"); self.struct = []; self.current = {}; self.dirty = False
        self.rebuilds = 0; self.depth = depth; self.queries = 0
        self.check_values()
        lines = []
        for f in prog.functions.values():
            if f.constant() is not None: continue
            for ins, o in f.rows.items():
                for _ in range(prog.teach): lines += self.gate_facts(f.name, [self.wire(v) for v in ins], o)[0]
        for m in prog.machines.values():
            for (q, s), val in m.rows.items():
                for _ in range(prog.teach): lines += self.step_facts(m, q, s, val)[0]
        if not lines: lines = ["mimic has nothing taught"]
        self.tmp = tempfile.TemporaryDirectory(); self.taught = lines
        t0 = time.time(); self.e = None; self.open_engine(); self.timing["learn_s"] = round(time.time() - t0, 2)
        self.taught_facts = len(lines); self.compiled = {}; self.machine_ent = {}

    def open_engine(self):
        """(Re)start the engine on the taught examples, plus, in rebuild mode, the structure and the current state."""
        if self.e is not None: self.e.close()
        lines = self.taught + (self.struct + [f for fs in self.current.values() for f in fs] if self.mode == "rebuild" else [])
        path = os.path.join(self.tmp.name, "kb.txt"); open(path, "w").write("\n".join(lines) + "\n")
        words = len({x for l in lines for x in l.split()})
        self.e = egm.open(path, settings=dict(SETTINGS, DEPTH=self.depth, MAXWORDS=max(12000, words + 1000)), binary=self.binary)
        self.e.relations(); self.dirty = False

    def add(self, lines):
        """Facts that stay (circuit structure, step links; in fresh mode, every step)."""
        if self.mode == "rebuild": self.struct += lines; self.dirty = True
        else: self.e.ingest_many(lines)

    def sync(self):
        if self.mode == "rebuild" and self.dirty: self.open_engine(); self.rebuilds += 1

    # names: e1, e2, ... ; values are prefixed so they can never collide with names or relation words
    def name(self): self.n += 1; return f"e{self.n}"
    @staticmethod
    def v(x): return "v" + x
    @staticmethod
    def unv(x): return x[1:]

    def check_values(self):
        vals = {o for f in self.p.functions.values() for o in list(f.rows.values()) + [x for r in f.rows for x in r]}
        if len(vals) > MAX_VALUES:
            raise MimicError(f"functions use {len(vals)} distinct values; the engine learns rules for at most {MAX_VALUES} "
                             f"values on one wire relation (studies/harness). Use fewer values.")
        for m in self.p.machines.values():
            states = {q for q, _ in m.rows} | {v[2] for v in m.rows.values()}
            syms = {s for _, s in m.rows} | {v[0] for v in m.rows.values()} | {m.blank}
            for what, xs in (("states (with halt)", states), ("symbols", syms)):
                if len(xs) > MAX_VALUES: raise MimicError(f"machine {m.name} has {len(xs)} {what}; at most {MAX_VALUES}")

    def wire(self, value=None):
        return (self.name(), value)

    def gate_facts(self, fname, inputs, out_value=None):
        """inputs: [(wire, value or None)]. Returns (lines, output wire)."""
        g, o = self.name(), self.name()
        L = [f"{o} is output of {g}", f"{g} has kind {fname}"]
        for i, (w, val) in enumerate(inputs):
            L.append(f"{g} has {SLOTS[i]} input {w}")
            if val is not None: L.append(f"{w} has value {self.v(val)}")
        if out_value is not None: L.append(f"{o} has value {self.v(out_value)}")
        return L, o

    # One single-token verb per machine and role. Phrases that differ in one word and share a tail ("reads inc symbol 1",
    # "has inc symbol 1") let the engine read the verb as the open slot instead of the value (lang/mimic/RESULTS.md).
    def rel(self, m, kind): return {"write": f"{m.name}_writes", "move": f"{m.name}_moves", "next": f"{m.name}_state"}[kind]

    def step_facts(self, m, q, s, outs=None):
        st, w, mv, nx = self.name(), self.name(), self.name(), self.name()
        L = [f"{w} is write of {st}", f"{mv} is move of {st}", f"{nx} is next of {st}"] + self.step_state(m, st, q, s)
        if outs:
            for i, (k, slot) in enumerate((("write", w), ("move", mv), ("next", nx))):
                L.append(f"{slot} {self.rel(m, k)} {self.v(outs[i])}")
        return L, {"step": st, "write": w, "move": mv, "next": nx}

    def step_state(self, m, st, q, s): return [f"{st} {m.name}_state {self.v(q)}", f"{st} {m.name}_reads {self.v(s)}"]

    def snapshot(self, record, facts):
        """The current state of a record: an OBSERVE snapshot, or (rebuild) the only state the next engine sees."""
        if self.mode == "rebuild": self.current[record] = list(facts); self.dirty = True
        else: self.t += 1; self.e.observe("mimic", record, self.t, facts=facts)

    def ask(self, pattern):
        self.sync(); self.queries += 1; vals = self.e.values(pattern, strict=True); return [self.unv(x) for x in vals]

    def proof(self, pattern):
        self.sync()
        for f in self.e.ask(pattern, strict=True):
            if f.status != "stated" and f.rule: return pretty(f.rule)
        return None

    # ---- machines
    def machine_step(self, m, q, s, trace):
        """Returns ({write, move, next} -> value or None, {kind: 'learned'|'declared'})."""
        if self.fresh or m.name not in self.machine_ent:
            L, slots = self.step_facts(m, q, s)
            if self.fresh: self.add(L)
            else:
                self.add(L[:3]); self.machine_ent[m.name] = slots; self.snapshot(slots["step"], L[3:])
        else:
            slots = self.machine_ent[m.name]; self.snapshot(slots["step"], self.step_state(m, slots["step"], q, s))
        got, how = {}, {}
        for i, k in enumerate(("write", "move", "next")):
            c = m.constant(i)
            if c is not None: got[k], how[k] = c, "declared"; continue
            a = self.ask(f"{slots[k]} {self.rel(m, k)} ?")
            got[k], how[k] = (a[0] if len(a) == 1 else None), "learned"
            if trace and got[k] is not None: how[k] = "learned: " + (self.proof(f"{slots[k]} {self.rel(m, k)} ?") or "")
        return got, how

    def run(self, m, tape_text, at="end", max_steps=1000, trace=False):
        tape = {i: c for i, c in enumerate(tape_text)}
        head = len(tape_text) - 1 if at == "end" else 0 if at == "start" else int(at)
        q, steps, t0 = m.start, 0, time.time()
        while q != "halt" and steps < max_steps:
            s = tape.get(head, m.blank)
            got, how = self.machine_step(m, q, s, trace)
            if None in got.values():
                known = {k: v for k, v in got.items() if v is not None}
                return {"status": "unknown", "steps": steps, "state": q, "symbol": s, "known": known,
                        "tape": render(tape, m.blank), "seconds": time.time() - t0}
            if trace: self.out(f"    step {steps + 1}: {q} reads {s} -> write {got['write']}, {got['move']}, go {got['next']}"
                               + "".join(f"\n        {k}: {h}" for k, h in how.items()))
            tape[head] = got["write"]; head += 1 if got["move"] == "right" else -1; q = got["next"]; steps += 1
        return {"status": "halted" if q == "halt" else "step limit", "steps": steps, "tape": render(tape, m.blank),
                "seconds": time.time() - t0, "declared": [k for k, i in (("write", 0), ("move", 1), ("next", 2)) if m.constant(i) is not None]}

    # ---- functions and circuits
    def compile(self, name):
        """Build a circuit (or a single function) once: its gates and input wires. Returns (inputs, outputs, declared)."""
        if name in self.compiled and not self.fresh: return self.compiled[name]
        if name in self.p.functions:
            f = self.p.functions[name]; ins = [f"x{i}" for i in range(f.arity)]
            c = Circuit(name, ins, ["out"]); c.body = [("out", name, ins, 0)]
        elif name in self.p.circuits: c = self.p.circuits[name]
        else: raise MimicError(f"no function or circuit named {name}")
        wires = {x: self.name() for x in c.ins}; L = []; declared = []
        if not hasattr(self, "label"): self.label = {}
        for target, fname, args, n in c.body:
            f = self.p.functions.get(fname)
            if not f: raise MimicError(f"line {n}: no function named {fname}")
            if len(args) != f.arity: raise MimicError(f"line {n}: {fname} takes {f.arity} inputs")
            for a in args:
                if a not in wires: raise MimicError(f"line {n}: {a} is not defined before this line")
            gl, o = self.gate_facts(fname, [(wires[a], None) for a in args])
            if f.constant() is not None: gl.append(f"{o} has value {self.v(f.constant())}"); declared.append(target)
            L += gl; wires[target] = o
        self.add(L); self.label.update({wv: f"{c.name}.{x}" for x, wv in wires.items()})
        res = ([wires[x] for x in c.ins], [(x, wires[x]) for x in c.outs], declared)
        self.compiled[name] = res; return res

    def evaluate(self, name, values, trace=False):
        ins, outs, declared = self.compile(name)
        if len(values) != len(ins): raise MimicError(f"{name} takes {len(ins)} inputs")
        t0 = time.time()
        facts = [f"{w} has value {self.v(x)}" for w, x in zip(ins, values)]
        if self.fresh: self.add(facts)
        else: self.snapshot("in_" + ins[0], facts)
        res = {}
        for label, w in outs:
            a = self.ask(f"{w} has value ?"); res[label] = a[0] if len(a) == 1 else None
            if trace and res[label] is not None: self.out(f"    {label} = {res[label]}: {self.proof(f'{w} has value ?') or 'declared'}")
        return res, time.time() - t0, declared

    def evaluate_demand(self, name, values):
        """Recursive questions: evaluate top-down. Ask for an output; if the engine can't answer at this depth, ask the
        engine which gate produces the wire and what its inputs are, evaluate those first (recursively), state their
        values, and ask again. Intermediate values computed this way are ingested as facts (labelled in results)."""
        c = self.p.circuits.get(name)
        self.compiled.pop(name, None); ins, outs, _ = self.compile(name)   # a fresh instance per evaluation
        self.add([f"{w} has value {self.v(x)}" for w, x in zip(ins, values)])
        memo, stated = {w: x for w, x in zip(ins, values)}, []
        def solve(w, depth=0):
            if w in memo: return memo[w]
            a = self.ask(f"{w} has value ?")
            if len(a) == 1: memo[w] = a[0]; return a[0]
            gs = self.ask_raw(f"{w} is output of ?")
            if len(gs) != 1: memo[w] = None; return None
            g = gs[0]; args = []
            for slot in SLOTS:
                x = self.ask_raw(f"{g} has {slot} input ?")
                if not x: break
                args.append(x[0])
            vals = [solve(x, depth + 1) for x in args]
            if None in vals: memo[w] = None; return None
            self.add([f"{x} has value {self.v(v)}" for x, v in zip(args, vals) if x not in stated]); stated.extend(args)
            a = self.ask(f"{w} has value ?"); memo[w] = a[0] if len(a) == 1 else None; return memo[w]
        return {label: solve(w) for label, w in outs}

    def ask_raw(self, pattern):
        """A question about structure (which gate, which inputs): stated facts, names returned as they are."""
        self.sync(); self.queries += 1
        return [f.object for f in self.e.ask(pattern) if f.status == "stated"]

    def why(self, pattern, depth=0, max_depth=12, seen=None):
        """Navigate the proof tree by asking for each premise in turn (recursive questions). Returns nested lines."""
        seen = set() if seen is None else seen
        self.sync(); lines = []
        for f in self.e.ask(pattern, strict=True):
            if f.status == "stated":
                lines.append(("  " * depth) + f"{self.named(f.fact)}  (given)"); continue
            if f.fact in seen or depth >= max_depth: lines.append(("  " * depth) + f"{self.named(f.fact)}  (...)"); continue
            seen.add(f.fact); lines.append(("  " * depth) + f"{self.named(f.fact)}  [{f.tier}]")
            for b in f.because or []:
                if " has value " in b and b.split()[0] != pattern.split()[0]:
                    lines += self.why(b.rsplit(" ", 1)[0] + " ?", depth + 1, max_depth, seen)
            break
        return lines

    def named(self, fact):
        w = fact.split()
        return " ".join([getattr(self, "label", {}).get(w[0], w[0])] + w[1:-1] + [re.sub(r"^v", "", w[-1])])

    def automaton(self, fname, width, steps, start):
        f = self.p.functions.get(fname)
        if not f or f.arity != 3: raise MimicError(f"automaton needs a 3-input function; {fname} isn't one")
        cells = [self.name() for _ in range(width)]; outs = []; L = []
        for i in range(width):
            gl, o = self.gate_facts(fname, [(cells[(i - 1) % width], None), (cells[i], None), (cells[(i + 1) % width], None)])
            L += gl; outs.append(o)
        self.add(L)
        row = list(start); rows = [row]; t0 = time.time()
        for _ in range(steps - 1):
            self.snapshot("row_" + cells[0], [f"{c} has value {self.v(x)}" for c, x in zip(cells, row)])
            nxt = []
            for o in outs:
                a = self.ask(f"{o} has value ?"); nxt.append(a[0] if len(a) == 1 else None)
            if None in nxt: return rows, "unknown", time.time() - t0
            row = nxt; rows.append(row)
        return rows, "ok", time.time() - t0

    # ---- what was learned
    def learned_report(self):
        """For each taught and hidden row: does the engine, on a fresh probe, give the row's output?"""
        rep = {}
        for f in self.p.functions.values():
            r = {"taught": len(f.rows), "learned": 0, "declared": f.constant() is not None, "hidden": {}}
            for rows, bucket in ((f.rows, None), (f.hidden, "hidden")):
                for ins, o in rows.items():
                    got = None if r["declared"] else self.evaluate(f.name, list(ins))[0]["out"]
                    if r["declared"]: got = f.constant()
                    if bucket is None: r["learned"] += got == o
                    else: r["hidden"][" ".join(ins)] = {"expected": o, "inferred": got}
            rep[f.name] = r
        for m in self.p.machines.values():
            r = {"taught": len(m.rows), "learned": 0, "hidden": {}}
            for rows, bucket in ((m.rows, None), (m.hidden, "hidden")):
                for (q, s), val in rows.items():
                    got, _ = self.machine_step(m, q, s, False); g = (got["write"], got["move"], got["next"])
                    if bucket is None: r["learned"] += g == val
                    else: r["hidden"][f"{q} {s}"] = {"expected": " ".join(val), "inferred": " ".join(x or "?" for x in g)}
            rep[m.name] = r
        return rep

    def rules_for(self, name):
        out = []
        self.sync()
        for r in self.e.rules():
            t = r.text
            if not t.startswith("TREE"): continue
            if name in self.p.functions and ("has kind ?](g," + name + ")") in t or (name in self.p.functions and "has kind" not in t and "is output of" in t):
                out.append((r.tier, r.known, r.agree, pretty(t)))
            if name in self.p.machines and f"{name}_" in t and any(f"is {k} of ?](a," in t for k in ("write", "move", "next")):
                out.append((r.tier, r.known, r.agree, pretty(t)))
        return out


def render(tape, blank):
    if not tape: return ""
    lo, hi = min(tape), max(tape); s = "".join(tape.get(i, blank) for i in range(lo, hi + 1))
    return s.strip(blank) or blank


def pretty_fact(f):
    return re.sub(r" v(\w+)$", r" \1", f)


def pretty(rule):
    t = rule.replace("TREE ", "")
    t = re.sub(r"\[\? (.*?) \?\]", r"\1", t)
    return re.sub(r",v(\w+)\)", r",\1)", t)   # values are stored as v<value>


# -------------------------------------------------------------------------------- driver
def execute(text, mode="fresh", out=print, binary=None):
    p = Program.parse(text); R = Runtime(p, mode=mode, out=out, binary=binary)
    out(f"mimic: taught {len(p.functions)} function(s), {len(p.machines)} machine(s): {R.taught_facts:,} example facts "
        f"({p.teach} per row); engine learned in {R.timing['learn_s']} s")
    log = {"mode": mode, "learn_s": R.timing["learn_s"], "taught_facts": R.taught_facts, "learned": R.learned_report(), "actions": []}
    for name, r in log["learned"].items():
        if r.get("declared"): out(f"  {name}: every taught row gives the same output, so it is declared, not inferred")
        else: out(f"  {name}: {r['learned']} of {r['taught']} taught rows learned")
        for k, h in r["hidden"].items():
            verdict = "inferred correctly" if h["inferred"] == h["expected"] else ("unknown" if h["inferred"] in (None, "? ? ?") or "?" in (h["inferred"] or "?") else "inferred differently")
            out(f"    untaught row {k}: you expect {h['expected']}, engine says {h['inferred'] or 'unknown'} ({verdict})")
    for n, kind, line in p.actions:
        w = line.split()
        if kind == "print": out(line[len("print"):].strip()); continue
        if kind == "rules":
            out(f"rules learned for {w[1]}:")
            for tier, known, agree, t in R.rules_for(w[1]): out(f"  [{tier}, {agree:.2f} on {known}] {t}")
            continue
        if kind == "run":
            m = p.machines.get(w[1])
            if not m: raise MimicError(f"line {n}: no machine named {w[1]}")
            at = w[w.index("at") + 1] if "at" in w else "end"; mx = int(w[w.index("max") + 1]) if "max" in w else 1000
            r = R.run(m, w[3], at=at, max_steps=mx, trace="trace" in w)
            if r["status"] == "unknown":
                out(f"run {m.name} on {w[3]}: UNKNOWN at step {r['steps'] + 1}: no learned rule decides state {r['state']} "
                    f"reading {r['symbol']} (known: {r['known'] or 'nothing'}); tape so far {r['tape']}")
            else:
                note = f" [declared: {', '.join(r['declared'])}]" if r["declared"] else ""
                out(f"run {m.name} on {w[3]}: {r['tape']}  ({r['status']} after {r['steps']} steps, "
                    f"{1000 * r['seconds'] / max(1, r['steps']):.0f} ms/step){note}")
            log["actions"].append({"line": n, "kind": "run", "program": m.name, "input": w[3], **{k: v for k, v in r.items() if k != "seconds"},
                                   "ms_per_step": round(1000 * r["seconds"] / max(1, r["steps"]), 1)})
        if kind == "why":
            args = w[2:]; R.evaluate(w[1], args); ins, outs, _ = R.compiled[w[1]]   # the instance just evaluated
            out(f"why {w[1]} {' '.join(args)}:")
            for label, wire in outs:
                out(f"  {label}:"); [out("    " + l) for l in R.why(f"{wire} has value ?")]
            continue
        if kind == "eval":
            args = [x for x in w[2:] if x != "trace"]
            res, dt, declared = R.evaluate(w[1], args, trace="trace" in w)
            shown = ", ".join(f"{k} = {v if v is not None else 'UNKNOWN'}" for k, v in res.items())
            out(f"eval {w[1]} {' '.join(args)}: {shown}" + (f"  [declared: {', '.join(declared)}]" if declared else ""))
            log["actions"].append({"line": n, "kind": "eval", "program": w[1], "input": args, "result": res, "ms": round(1000 * dt, 1)})
        if kind == "automaton":
            width = int(w[w.index("width") + 1]); steps = int(w[w.index("steps") + 1]); start = w[w.index("start") + 1]
            if start == "single": start = "0" * (width - 1) + "1"
            if len(start) != width: raise MimicError(f"line {n}: start pattern must have {width} cells")
            rows, status, dt = R.automaton(w[1], width, steps, list(start))
            out(f"automaton {w[1]} ({status}, {1000 * dt / max(1, len(rows) - 1):.0f} ms/step):")
            for r in rows: out("  " + "".join("#" if c == "1" else "." if c == "0" else c for c in r))
            log["actions"].append({"line": n, "kind": "automaton", "program": w[1], "rows": ["".join(r) for r in rows], "status": status})
    log["rebuilds"] = R.rebuilds
    R.e.close(); R.tmp.cleanup()
    return log


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0
    path = a[0]
    if not os.path.isfile(path):
        guess = path.rstrip(".,;:")   # a path copied with the sentence's punctuation
        hint = f"; did you mean {guess}?" if guess != path and os.path.isfile(guess) else ""
        print(f"mimic: no such file: {path}{hint}", file=sys.stderr); return 1
    try:
        mode = a[a.index("--mode") + 1] if "--mode" in a else "fresh"
        execute(open(path).read(), mode=mode, out=(lambda s: None) if "--quiet" in a else print)
    except MimicError as e:
        print(f"mimic: {e}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
