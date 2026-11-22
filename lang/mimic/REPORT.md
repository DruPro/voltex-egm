# Mimic: research report

Mimic is a small programming language whose operations are learned, not written. This report covers what it is,
how it runs on the engine, what its pre-registered bench measured, and what building it revealed about the engine.
The user guide is `README.md`; the measurements are in `bench/`.

## 1. The idea

- **You teach by showing.** A function is a few rows of its table; a machine is a few of its transitions. Voltex
  EGM learns rules from those examples; nothing in Mimic says what any operation means.
- **The learned rules are the program.** Running a program means applying the rules to an initial state and
  iterating (`studies/inferred_program`). Every value a program produces has a proof, back to your inputs and to the
  examples behind each rule.
- **It never guesses.** When no law-tier rule decides a step, the run stops and says UNKNOWN. An output that is the
  same in every example can't be learned (it never varies), so Mimic applies it as declared and labels it.

## 2. How a program becomes facts

| Mimic | Facts the engine learns from (each row × 64) |
|---|---|
| `function f`, row `0 1 -> 1` | a gate `g`: `o is output of g`, `g has kind f`, `g has first input w1`, `w1 has value v0`, … `o has value v1` |
| `machine m`, row `A 0 -> 1 right B` | a step `s`: `s m_state mvA`, `s m_reads mv0`, and slots `w is write of s` (`w m_writes mv1`), `n is next of s` (`n m_state mvB`) |
| `circuit` | gates wired to each other's output wires; compiled once |
| `automaton f …` | one row of cells; each cell is a gate of `f` reading its neighbours |

Each encoding choice is a measured constraint, not a style:
- **At most 8 distinct values per learned output relation.** The tree search skips larger targets
  (`studies/harness`).
- **One single-token verb per machine and role** (`inc_reads`, `inc_writes`). Phrases that differ in one word and
  share a tail made the engine read the verb as the open slot.
- **Machine values carry the machine's name** (`incv1`). Without it, a machine taught next to a function that also
  uses 0 and 1 lost its blank-symbol transition (§5.3).
- **About 64 examples per row.** Majority values take the most data to confirm, because evidence is measured
  against the base rate.

## 3. Execution modes

| Mode | State change between steps | Learned rules across steps | Result on the bench |
|---|---|---|---|
| `fresh` (default) | new entities every step | relearned every step | 26/28 right, 0 wrong; 11-13 ms per machine step, growing with run length (10.6 → 19.3 ms over 4 → 256 steps) |
| `refresh` | one entity; old state retracted, new ingested, same names; `REFRESH` on | **kept** | the same 26/28, 0 wrong; busy beaver 39 → 12 ms per step; flat per-step cost (exploratory) |
| `rebuild` | a new engine from the examples plus the current state | relearned | 26/28, 0 wrong; about 2× `fresh` |
| `observe` | one entity, OBSERVE snapshots | relearned | 25/28: the engine loses a record's current snapshot after 13-26 restatements (§5.2) |

The two unknowns in every mode are the rows `guess.mim` deliberately withholds.

## 4. Bench results (`bench/`, pre-registered)

- **Learning:** 8 programs, 14 functions and machines (1 to 3 inputs, up to 6 transitions, 60 taught rows). All 14
  were learned to 100% of their taught rows, checked on fresh probes.
- **Correctness:** every `eval`, `run` and `automaton` was checked against a literal interpreter of the same tables.
  There were 0 wrong results in any mode.
- **Recursive questions** (`why`, and a top-down evaluator that asks for each gate's inputs) matched the engine's
  own chained inference at `DEPTH 0`, at 13× the questions and 7× the time. They're redundant for computing;
  `why` stays, for reading proofs.
- **Untaught rows:** the engine abstained instead of generalising to the withheld rows.
- **Verdicts:** P1-P5 all pass (`bench/RESULTS.md`). The `refresh` mode and the namespacing re-check came after the
  pre-registration and are labelled exploratory (`bench/results_refresh_mode.json`,
  `bench/results_after_namespacing.json`: the same 26/28, 0 wrong, in every mode).

## 5. What building it revealed about the engine

1. **Rebuild on every change.** Any new fact made the next question relearn categories, relations and rules: about
   85% of a step's time at 12,288 taught facts. That led to `studies/inferred_program`, and then to the engine
   change in `studies/refresh_trees`: `REFRESH` keeps learned rules, tree rules included, across small state changes.
2. **OBSERVE snapshot loss.** A record's current snapshot facts disappear after 13 restatements with one fact per
   snapshot, or 26 with two, when plain facts also name the entity. It reproduces on a plain engine
   (`repro_observe_loss.py`). Reported; not fixed.
3. **Silent loss through categories.** Taught next to a `not` function, the increment machine's `inc_reads` relation
   went from 192 facts to 128. The 64 facts reading `_` were dropped, and with them the rules for the blank symbol.
   - **Why:** the engine groups words that appear in similar contexts. Once `not` also used 0 and 1, `_` no longer
     shared their contexts and left their category. A fact whose value is outside the slot's category belongs to no
     relation.
   - **Nothing reports it.** Mimic now namespaces machine values; the engine behaviour is reported for the owner.
4. **Constant outputs.** An output that never varies can't be learned as a rule: there is nothing to beat the base
   rate with. That is information, not a bug; Mimic declares such outputs.
5. **Phrasing.** Relation phrases must not differ in only one word with a shared tail.

## 6. What Mimic shows about Voltex, and what it doesn't

- **It shows:**
  - operations can be taught by examples and executed as learned rules: circuits 17 gates deep, a busy beaver,
    binary increment with tape growth, and Rule 110;
  - every result has a proof;
  - the engine abstains instead of guessing;
  - learned rules can now stay fixed while a program runs (`refresh` mode).
- **It doesn't show:**
  - generalisation beyond what the examples determine: withheld rows stay unknown, by design;
  - scale: these are small knowledge bases, a few thousand taught facts;
  - Turing completeness of the engine alone. Unbounded computation comes from Mimic acting as the harness, which
    holds the tape and the clock (`studies/compute`, `studies/harness`).
- **Still costly:** each step re-projects relations and reruns inference over everything taught. Inference that
  touches only what changed would be the next step; it isn't built.

## 7. Try it

```
python3 lang/mimic/play.py                       # the guided tour, then a prompt
python3 lang/mimic/mimic.py lang/mimic/examples/busy_beaver.mim --mode refresh
```
