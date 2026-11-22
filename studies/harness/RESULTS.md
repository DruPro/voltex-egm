# Learn once, compute later: results

Pre-registered: `PREREGISTRATION.md` (round 1) and `PREREGISTRATION_R2.md` (round 2); hashes in `prereg_hash.txt`.
Why there are two rounds: `DEVIATIONS.md`. Numbers come from `results/` (round 2) and `results_r1/` (round 1),
written by `tools/run.py`. No engine change; the harness is `tools/harness.py`, outside the engine.

## Verdicts

| Prediction | Round 1 | Round 2 |
|---|---|---|
| H1a learn once, compute later: 30 new 8-bit adders, ingest and ask | pass | **pass** |
| H1b every rule unchanged after ingesting the adders | fail | fail (replaced by H1b') |
| H1b' rules about wire values unchanged | - | **pass** |
| H2 at every amount of data: 0 wrong (too little data shows as unanswered) | pass | **pass** |
| H3a busy beaver (3 states): 14 steps, same tape and head as the simulator | fail | **pass** |
| H3b binary increment on 48 inputs of 1-16 bits (tape grows) | fail | **pass** |
| H3c every rule unchanged during runs | fail | **pass** |
| H3c' rules about step outputs unchanged | - | **pass** |
| H4 an untaught transition: stop with "unknown", never invent | fail | **pass** |

Round 1 failed on the Turing machine for one reason: all outputs shared one relation with 10 distinct values, and
the tree search only considers targets with at most 8 (`DEVIATIONS.md` 1). One relation per kind of value fixed it.

## 1. Learn once, compute later

A knowledge base was taught 700 example gates. Then each new 8-bit adder was given to it as only its wiring and
primary inputs: 177 facts. Its 9 outputs were then asked for.
- **Results:** 270 of 270 outputs right, 0 wrong.
- **Time:** ingest and query took 0.21 s median per circuit, 0.13-0.30 s.
- **Rules:** the rules about values didn't change. The engine did learn 2 new true rules about the circuits' wiring
  ("a gate fed by an AND gate's output is an OR gate"). Learning doesn't stop after teaching; it keeps using what
  it ingests.

## 2. How much data teaching takes

**Gates:** k example gates per kind; then 10 8-bit adders and 20 multiplexers, 110 outputs per seed, over 3 seeds.

| Examples per kind | Right | Wrong | Unanswered |
|---|---|---|---|
| 2 | 0 / 330 | 0 | 330 |
| 4 | 0 / 330 | 0 | 330 |
| 8 | 0 / 330 | 0 | 330 |
| 16 | 0 / 330 | 0 | 330 |
| 32 | 11 / 330 | 0 | 319 |
| 64 | 134 / 330 | 0 | 196 |
| 100 | 263 / 330 | 0 | 67 |
| 200 | 330 / 330 | 0 | 0 |

**Turing machine:** k example steps per transition; then the busy beaver and 16 increments, 17 runs per seed, over
3 seeds.

| Examples per transition | Runs correct | Runs wrong | Stopped "unknown" |
|---|---|---|---|
| 8 | 0 / 51 | 0 | 51 |
| 16 | 0 / 51 | 0 | 51 |
| 32 | 0 / 51 | 0 | 51 |
| 64 | 51 / 51 | 0 | 0 |
| 100 | 51 / 51 | 0 | 0 |

- **No guessing with too little data.** At every amount of data, nothing was wrong: what the engine can't yet
  support stays unanswered.
- **The majority value takes the most data.** "Write one" happens in 7 of 9 transitions, and acceptance is
  measured against the base rate. A rule predicting the common value barely beats chance until there are many
  examples, so it is the last to be accepted. In the exploratory probes (`DEVIATIONS.md` 1), next state and
  direction were exact for all 9 transitions at 16 examples per transition; write needed 64.

## 3. The harness loop: a Turing machine whose transition table was learned

The engine was never shown a run, only isolated example steps. The harness held the tape and the clock. Each step
it created one new step entity, ingested it, asked for its three outputs, and applied them.

- **Busy beaver:** 14 steps, halting with six ones (`111111`),
  identical to the simulator in every seed. 1.2-1.2 s per run, about 86 ms per step.
- **Binary increment:** all 48 inputs correct, including all-ones inputs. There the carry runs past the input and
  the harness extends the tape. Runs of 1-17 steps, nothing laid out in advance.
- **The learned transition table** (21 rules, seed 0):

  | Rule (step `g`, output slot `a`) | Tier |
  |---|---|
| `is move of(a,g) & has state(g,A) => has direction(a,right)` | law |
| `is move of(a,g) & has state(g,B) => has direction(a,right)` | law |
| `is move of(a,g) & has state(g,C) => has direction(a,left)` | law |
| `is move of(a,g) & has state(g,carry) => has direction(a,left)` | law |
| `is move of(a,g) & reads(g,blank) => has direction(a,left)` | law |
| `is next of(a,g) & has state(g,A) & reads(g,one) => has state(a,halt)` | law |
| `is next of(a,g) & has state(g,A) & reads(g,zero) => has state(a,B)` | law |
| `is next of(a,g) & has state(g,B) & reads(g,one) => has state(a,B)` | law |
| `is next of(a,g) & has state(g,B) & reads(g,zero) => has state(a,C)` | law |
| `is next of(a,g) & has state(g,C) & reads(g,one) => has state(a,A)` | law |
| `is next of(a,g) & has state(g,C) & reads(g,zero) => has state(a,C)` | law |
| `is next of(a,g) & has state(g,carry) & reads(g,one) => has state(a,carry)` | law |
| `is next of(a,g) & has state(g,carry) & reads(g,zero) => has state(a,halt)` | law |
| `is next of(a,g) & reads(g,blank) => has state(a,halt)` | law |
| `is write of(a,g) & has state(g,A) => has symbol(a,one)` | law |
| `is write of(a,g) & has state(g,B) & reads(g,one) => has symbol(a,one)` | law |
| `is write of(a,g) & has state(g,B) & reads(g,zero) => has symbol(a,zero)` | law |
| `is write of(a,g) & has state(g,C) => has symbol(a,one)` | law |
| `is write of(a,g) & has state(g,carry) & reads(g,one) => has symbol(a,zero)` | law |
| `is write of(a,g) & has state(g,carry) & reads(g,zero) => has symbol(a,one)` | law |
| `is write of(a,g) & reads(g,blank) => has symbol(a,one)` | law |

## 4. The control: a transition never taught

Increment was taught without `(carry, blank)`.
- **All-ones inputs:** all 15 stopped "unknown" at exactly the step that needs it.
- **Inputs with a zero:** all 33 completed correctly.
- **What the engine answered at the untaught step:** {'write': [], 'move': ['left'], 'next': []}. It gave the direction: "the carry state
  always moves left" was learned at law tier from the taught transitions. It left write and next state unanswered,
  because nothing determines them. The harness stopped, as specified, instead of filling them in.

## What this shows, and what it doesn't

- **Data alone taught the step functions.** Gates and a Turing machine's transition table were learned from
  examples, as rules with proofs, with no tables or code given.
- **Learned knowledge computes new results from the minimal new data:** one circuit's wiring, or one step entity.
- **Engine plus harness runs computations whose length the data never fixed:** a busy beaver, and increments that
  grow the tape. The engine supplies a learned, finite transition function. The harness supplies memory and
  iteration, the part inference can't (`studies/compute`). The combination is a Turing machine whose control was
  learned from data. The unbounded part is the harness, not the engine.
- **Limits:**
  - **Representation:** tree targets need at most 8 distinct values (now in the capability matrix).
  - **Data:** majority values need the most examples.
  - **Cost:** about 86 ms per step, because every step rebuilds the knowledge
    base (`studies/scaling` I1: new names cost a rebuild). A long computation would need incremental inference.
  - **Scope:** two small programs, not a general proof. Without the harness's loop, the engine alone remains
    bounded.
