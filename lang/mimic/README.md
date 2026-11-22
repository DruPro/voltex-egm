# Mimic: a programming language you teach by example

In Mimic you never write what an operation does. You **show** it. The Voltex EGM engine learns rules from your
examples, and every step a program takes is decided by a learned rule, with a proof you can ask for. When nothing
learned decides a step, the program stops and says **unknown**. It never guesses.

```
python3 lang/mimic/mimic.py lang/mimic/examples/hello.mim
```

## Ten-second tour

```
function and            # show the table; nothing says what "and" means
  0 0 -> 0
  0 1 -> 0
  1 0 -> 0
  1 1 -> 1
end

function not
  0 -> 1
  1 -> 0
end

circuit nand a b -> out
  t = and a b
  out = not t
end

eval nand 1 1           # out = 0, computed by learned rules
why nand 1 1            # walk the proof back to your inputs
rules and               # what the engine learned
```

What it prints for `rules and`:

```
[law, 1.00 on 128] is output of(a,g) & has kind(g,and) & has first input(g,y1) & has value(y1,0) => has value(a,0)
[law, 1.00 on 64]  is output of(a,g) & has first input(g,y1) & has value(y1,1) & has second input(g,y2) & has value(y2,1) => has value(a,1)
...
```

The engine didn't memorise your four rows. It found **"an AND with any 0 input gives 0"** on its own: a minimised
rule, like a Karnaugh map.

## The language

| Statement | What it does |
|---|---|
| `function NAME` … `end` | rows `inputs -> output` (1 to 3 inputs) |
| `machine NAME` … `end` | `start STATE`, `blank _`, transitions `STATE SYMBOL -> WRITE left/right NEXT` (`halt` stops) |
| `circuit NAME a b -> s c` … `end` | wires: `t = xor a b`, using functions |
| `eval NAME 1 0 [trace]` | evaluate a circuit or function; `trace` prints the rule behind each output |
| `run NAME on 1011 [at start\|end\|N] [max N] [trace]` | run a machine on a tape, one character per symbol |
| `automaton NAME width W steps T start PATTERN\|single` | a row of cells updated by a 3-input function |
| `why NAME 1 0` | evaluate, then walk the proof of each output down to your inputs |
| `rules NAME` | the rules the engine learned |
| `? row` | a row you know but don't teach: Mimic reports what the engine infers for it |
| `teach N` | examples per taught row (default 64) |

## What you'll see, and what it means

- **"3 of 3 taught rows learned".** After teaching, Mimic tests every row on a fresh probe. A row counts as learned
  only if a law-tier rule gives its output.
- **"declared, not inferred".** An output that is the same in every row (a machine that always moves right) can't
  be learned: nothing shows what it depends on, so no rule beats the base rate. Mimic applies it as you declared it,
  and labels it so.
- **"UNKNOWN at step 15".** No learned rule decides that step. The run stops there; Mimic doesn't fill it in.
- **"untaught row 1 1 0: you expect 1, engine says 1 (inferred correctly)".** The engine generalised from the rows
  it saw. It can also say "unknown", or "inferred differently" when your intended meaning isn't the simplest rule
  consistent with your rows.

## A taste: Rule 110 from eight shown rows

`examples/rule110.mim` shows the 8 cases of Rule 110 once. The engine learns 6 minimised rules, each holding on
every known case, and draws this:

```
...............................#
..............................##
.............................###
............................##.#
...........................#####
..........................##...#
.........................###..##
........................##.#.###
.......................#######.#
```

## How it runs: three modes

`--mode fresh|rebuild|observe`. All three teach the engine the same examples. Measured in `bench/RESULTS.md`
(pre-registered; every result checked against a literal interpreter):

| Mode | A machine step, or an `eval` | Correct | Cost per step |
|---|---|---|---|
| `fresh` (default) | new entities for every step, added to the running engine | 26/28, 0 wrong (the 2 unknowns are untaught rows) | 11-13 ms, flat to 64 steps |
| `rebuild` | a new engine from the taught examples plus only the current state | 26/28, 0 wrong | about 22 ms: relearns every step |
| `observe` | one entity, its state restated as an OBSERVE snapshot | 25/28, 0 wrong | 11-13 ms, but it stops after about 22 steps: the engine loses a record's current snapshot after 13-26 restatements (`repro_observe_loss.py`) |

## Why the rules look like that (engine boundaries you'll meet)

- **Values per relation.** At most 8 distinct values on one wire relation, and at most 8 states or symbols per
  machine. That's the tree search's limit for a target (`studies/harness`).
- **Inputs per function.** 1 to 3 inputs (tree rules join a few branches at one entity).
- **Examples per row.** About 64. Values that appear in most rows take the most examples to confirm, because
  evidence is measured against the base rate (`studies/harness`, H2).
- **Computation length.** Unbounded for machines: Mimic is the harness that holds the tape and the clock. The engine
  supplies the learned transition table (`studies/compute`, `studies/harness`).

## Examples

`examples/`:

| Program | Shows |
|---|---|
| `hello.mim` | two learned gates, a NAND built from them, `trace`, `rules` |
| `adder.mim` | a full adder; `why` walks the proof |
| `add8.mim` | an 8-bit ripple-carry adder, 17 gates deep |
| `increment.mim` | binary increment as a Turing machine, including a 16-bit carry |
| `busy_beaver.mim` | the 3-state busy beaver: 14 steps, six ones |
| `parity.mim` | a finite-state machine, with a declared (constant) move |
| `rule110.mim` | Rule 110, Turing complete in the limit, drawn as a pattern |
| `guess.mim` | rows withheld from the engine: what does it infer? |

## Measured (`bench/`)

- **Learning:** 14 functions and machines in 8 programs, all learned to 100% of their taught rows.
- **Results:** 0 wrong results in any mode. Every undecided step was reported as unknown.
- **Recursive questions** (`why`, and a top-down evaluator that asks for each gate's inputs) reach the same results as
  the engine's own chained inference, at about 13× the questions. They're useful for reading proofs, and redundant
  for computing.
- **Untaught rows:** the engine abstained on the ones it was never shown, instead of guessing.

Run the bench: `python3 lang/mimic/bench/bench.py`, then `python3 lang/mimic/bench/report.py`.
