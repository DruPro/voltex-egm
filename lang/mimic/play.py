"""Mimic playground: watch the engine learn a program from examples, then run it.

  python3 lang/mimic/play.py            a guided tour, then an interactive prompt
  python3 lang/mimic/play.py --tour     the tour only          --repl   the prompt only
  python3 lang/mimic/play.py --fast     no animation delays    --no-color

Everything you see is computed by rules the engine learned from the rows shown on screen. Nothing in this file
knows what XOR, a Turing machine or Rule 110 is; it only draws what the engine answers.
"""
import os, re, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mimic  # noqa: E402

A = sys.argv[1:]
FAST = "--fast" in A
COLOR = sys.stdout.isatty() and "--no-color" not in A and os.environ.get("NO_COLOR") is None
def c(code, s): return f"\033[{code}m{s}\033[0m" if COLOR else s
B, DIM, GREEN, YELLOW, CYAN, MAG, RED = (lambda s: c("1", s)), (lambda s: c("2", s)), (lambda s: c("32", s)), \
    (lambda s: c("33", s)), (lambda s: c("36", s)), (lambda s: c("35", s)), (lambda s: c("31", s))
def pause(t): 0 if FAST else time.sleep(t)
def say(s=""): print(s, flush=True)


def runtime(text):
    p = mimic.Program.parse(text)
    return p, mimic.Runtime(p, mode="refresh", out=lambda s: None)


def show_learning(p, R):
    rep = R.learned_report()
    for name, r in rep.items():
        if r.get("declared"): say(f"  {CYAN(name)}: every row gives the same output, so it is {YELLOW('declared')}, not inferred")
        else:
            ok = r["learned"] == r["taught"]
            msg = f"{r['learned']} of {r['taught']} rows learned"
            say(f"  {CYAN(name)}: {(GREEN if ok else YELLOW)(msg)}")
        for k, h in r["hidden"].items():
            got = h["inferred"]; unk = got is None or "?" in (got or "?")
            say(f"    row {k} was never shown: you expect {h['expected']}, engine says "
                + (DIM("unknown (it won't guess)") if unk else (GREEN(got) if got == h["expected"] else YELLOW(got))))


def show_rules(R, name, limit=6):
    rs = R.rules_for(name)
    for tier, known, agree, t in rs[:limit]:
        say(f"    {DIM(f'[{tier}, {agree:.2f} on {known}]')} {short_rule(t)}")
    if len(rs) > limit: say(DIM(f"    ... {len(rs) - limit} more (type: rules {name})"))


def short_rule(t):
    t = re.sub(r"is output of\(a,g\) & ", "", t)
    t = re.sub(r"has (first|second|third) input\(g,(y\d)\) & has value\(\2,(\w+)\)", lambda m: f"{m.group(1)}={m.group(3)}", t)
    t = re.sub(r"has kind\(g,(\w+)\)", r"kind=\1", t)
    t = re.sub(r"=> has value\(a,(\w+)\)", r"=> output \1", t)
    t = re.sub(r"is (write|move|next) of\(a,g\) & ", "", t)
    t = re.sub(r"\w+_reads\(g,(\w+)\)", r"reading \1", t); t = re.sub(r"\w+_state\(g,(\w+)\)", r"in state \1", t)
    t = re.sub(r"=> \w+_writes\(a,(\w+)\)", r"=> write \1", t); t = re.sub(r"=> \w+_state\(a,(\w+)\)", r"=> go \1", t)
    return t.replace(" & ", ", ")


def animate_run(R, m, tape_text, at="end", max_steps=200):
    tape = {i: ch for i, ch in enumerate(tape_text)}
    head = len(tape_text) - 1 if at == "end" else 0 if at == "start" else int(at)
    q, steps, t0 = m.start, 0, time.time()
    def draw(note=""):
        lo, hi = min(list(tape) + [head]) - 1, max(list(tape) + [head]) + 1
        cells = "".join((MAG(f"[{tape.get(i, m.blank)}]") if i == head else f" {tape.get(i, m.blank)} ") for i in range(lo, hi + 1))
        say(f"   {cells}   {DIM(note)}")
    draw(f"start in {q}")
    while q != "halt" and steps < max_steps:
        s = tape.get(head, m.blank)
        got, how = R.machine_step(m, q, s, False)
        if None in got.values():
            say(RED(f"   UNKNOWN: no learned rule decides state {q} reading {s}. The run stops here; Mimic won't guess."))
            return
        tape[head] = got["write"]; head += 1 if got["move"] == "right" else -1
        steps += 1; prev, q = q, got["next"]
        draw(f"step {steps}: {prev} read {s} -> write {got['write']}, {got['move']}, go {q}"); pause(0.12)
    say(GREEN(f"   halted after {steps} steps") + DIM(f"  ({1000 * (time.time() - t0) / max(1, steps):.0f} ms per step, engine time)"))


def animate_automaton(R, fname, width, steps, start):
    rows, status, dt = R.automaton(fname, width, steps, list(start))
    for r in rows:
        say("   " + "".join(CYAN("█") if ch == "1" else DIM("·") for ch in r)); pause(0.06)
    if status != "ok": say(RED("   stopped: a cell no learned rule decides"))


def why(R, name, args):
    R.evaluate(name, args); ins, outs, _ = R.compiled[name]
    for label, wire in outs:
        for line in R.why(f"{wire} has value ?"):
            indent = len(line) - len(line.lstrip())
            body = line.strip().replace(f"{name}.", "")
            mark = GREEN(" given") if body.endswith("(given)") else ""
            say("    " + " " * indent + body.replace("  (given)", "").replace("  [law]", "") + (DIM("  [learned rule]") if "[law]" in line else "") + mark)


# ------------------------------------------------------------------ the tour
TOUR = [
    ("1. Show it a table. Nothing says what XOR means.", """function xor
  0 0 -> 0
  0 1 -> 1
  1 0 -> 1
  1 1 -> 0
end
function and
  0 0 -> 0
  0 1 -> 0
  1 0 -> 0
  1 1 -> 1
end
function or
  0 0 -> 0
  0 1 -> 1
  1 0 -> 1
  1 1 -> 1
end
circuit fulladd a b cin -> sum cout
  t = xor a b
  sum = xor t cin
  u = and a b
  v = and t cin
  cout = or u v
end""", "adder"),
    ("2. Show it three Turing-machine transitions: binary increment.", """machine inc
  start carry
  blank _
  carry 1 -> 0 left carry
  carry 0 -> 1 left halt
  carry _ -> 1 left halt
end""", "inc"),
    ("3. The 3-state busy beaver: six transitions, no other hint.", """machine bb
  start A
  blank 0
  A 0 -> 1 right B
  A 1 -> 1 right halt
  B 0 -> 0 right C
  B 1 -> 1 right B
  C 0 -> 1 left C
  C 1 -> 1 left A
end""", "bb"),
    ("4. Rule 110, a cellular automaton that is Turing complete in the limit: its eight cases, once.", """function rule110
  1 1 1 -> 0
  1 1 0 -> 1
  1 0 1 -> 1
  1 0 0 -> 0
  0 1 1 -> 1
  0 1 0 -> 1
  0 0 1 -> 1
  0 0 0 -> 0
end""", "r110"),
    ("5. What does it do with a case you never showed it?", """machine inc
  start carry
  blank _
  carry 1 -> 0 left carry
  carry 0 -> 1 left halt
  ? carry _ -> 1 left halt
end""", "guess"),
]


def tour():
    say(B("Mimic playground") + DIM("  — every result below is computed by rules the engine learned from the rows shown."))
    for title, text, kind in TOUR:
        say(); say(B(title)); pause(0.3)
        for line in text.splitlines(): say(DIM("   │ ") + line)
        p, R = runtime(text); say(DIM(f"   learned from {R.taught_facts:,} example facts ({p.teach} per row) in {R.timing.get('learn_s', 0) or 0:.2f} s:"))
        show_learning(p, R)
        if kind == "adder":
            say(DIM("   rules it found for xor (note: minimised, not a copy of the table):")); show_rules(R, "xor", 4)
            say("   " + B("1 + 1 + 1 in binary:"))
            res = R.evaluate("fulladd", ["1", "1", "1"])[0]; say(f"    sum = {GREEN(res['sum'])}, carry = {GREEN(res['cout'])}   (3 = binary 11)")
            say(DIM("   why? each value back to your inputs:")); why(R, "fulladd", ["1", "1", "1"])
        if kind == "inc":
            say(DIM("   the machine it learned:")); show_rules(R, "inc", 6)
            say("   " + B("run inc on 1011 (11 + 1):")); animate_run(R, p.machines["inc"], "1011")
            say("   " + B("run inc on 1111 (the tape has to grow):")); animate_run(R, p.machines["inc"], "1111")
        if kind == "bb":
            say("   " + B("run bb on a blank tape:")); animate_run(R, p.machines["bb"], "0", at="start")
        if kind == "r110":
            say("   " + B("32 cells, 16 steps, one live cell at the right:")); animate_automaton(R, "rule110", 32, 16, "0" * 31 + "1")
        if kind == "guess":
            say("   " + B("run inc on 1011 (doesn't need the missing case):")); animate_run(R, p.machines["inc"], "1011")
            say("   " + B("run inc on 111 (needs it):")); animate_run(R, p.machines["inc"], "111")
        R.e.close(); pause(0.4)
    say(); say(B("That's the tour.") + " Type " + CYAN("help") + " to write your own, or " + CYAN("quit") + ".")


# ------------------------------------------------------------------ the prompt
HELP = f"""{B('Teach')} (multi-line blocks end with {CYAN('end')}):
  {CYAN('function NAME')}  rows like  0 1 -> 1           {CYAN('machine NAME')}  start S, blank _, rows like  S 1 -> 0 left S2
  {CYAN('circuit NAME a b -> out')}  lines like  t = xor a b
{B('Run')}:
  {CYAN('eval NAME 1 0')}        {CYAN('why NAME 1 0')}        {CYAN('run NAME on 1011 [at start]')}        {CYAN('automaton NAME width 32 steps 16 start single')}
{B('Look')}:
  {CYAN('rules NAME')}   {CYAN('learned')}   {CYAN('show')} (the program so far)   {CYAN('load FILE')}   {CYAN('save FILE')}   {CYAN('reset')}   {CYAN('tour')}   {CYAN('quit')}
Rows marked {CYAN('?')} are kept from the engine: you'll see what it infers for them."""


def repl():
    blocks, state = [], {"p": None, "R": None}
    def rebuild():
        if state["R"]: state["R"].e.close()
        state["p"], state["R"] = runtime("\n".join(blocks)) if blocks else (None, None)
        if state["R"]: show_learning(state["p"], state["R"])
    say(DIM("type help for the language; definitions are taught as soon as you finish a block"))
    buf = []
    while True:
        try: line = input(CYAN("... ") if buf else CYAN("mimic> "))
        except (EOFError, KeyboardInterrupt): say(); return
        w = line.split()
        if buf:
            buf.append(line)
            if line.strip() == "end":
                try: mimic.Program.parse("\n".join(buf)); blocks.append("\n".join(buf)); rebuild()
                except mimic.MimicError as e: say(RED(f"  {e}"))
                buf = []
            continue
        if not w: continue
        try:
            if w[0] in ("quit", "exit"): return
            elif w[0] == "help": say(HELP)
            elif w[0] == "tour": tour()
            elif w[0] in ("function", "machine", "circuit"): buf = [line]
            elif w[0] == "reset": blocks.clear(); rebuild(); say(DIM("  forgotten"))
            elif w[0] == "show": say("\n".join(blocks) or DIM("  (nothing taught yet)"))
            elif w[0] == "load":
                text = open(w[1]).read(); p = mimic.Program.parse(text)
                blocks.append("\n".join(l for l in text.splitlines() if l.split() and l.split()[0] not in ("run", "eval", "automaton", "rules", "print", "why")))
                rebuild(); say(DIM(f"  loaded {len(p.functions)} function(s), {len(p.machines)} machine(s), {len(p.circuits)} circuit(s)"))
            elif w[0] == "save": open(w[1], "w").write("\n\n".join(blocks) + "\n"); say(DIM(f"  saved to {w[1]}"))
            elif not state["R"]: say(YELLOW("  teach something first (try: tour, or load lang/mimic/examples/adder.mim)"))
            elif w[0] == "learned": show_learning(state["p"], state["R"])
            elif w[0] == "rules": show_rules(state["R"], w[1], limit=50)
            elif w[0] == "eval":
                res = state["R"].evaluate(w[1], w[2:])[0]
                say("  " + ", ".join(f"{k} = {GREEN(v) if v is not None else RED('UNKNOWN')}" for k, v in res.items()))
            elif w[0] == "why": why(state["R"], w[1], w[2:])
            elif w[0] == "run":
                m = state["p"].machines.get(w[1])
                if not m: say(RED(f"  no machine named {w[1]}")); continue
                animate_run(state["R"], m, w[3], at=w[w.index("at") + 1] if "at" in w else "end")
            elif w[0] == "automaton":
                width, steps, start = int(w[w.index("width") + 1]), int(w[w.index("steps") + 1]), w[w.index("start") + 1]
                if start == "single": start = "0" * (width - 1) + "1"
                animate_automaton(state["R"], w[1], width, steps, start)
            else: say(YELLOW(f"  unknown command {w[0]!r}; type help"))
        except (mimic.MimicError, ValueError, IndexError, KeyError, FileNotFoundError) as e:
            say(RED(f"  {e}"))


if __name__ == "__main__":
    if "--repl" not in A: tour()
    if "--tour" not in A: repl()
