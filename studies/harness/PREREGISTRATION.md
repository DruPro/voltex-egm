# Learn once, compute later: a harness that gives the engine memory and a clock

Status: pre-registered before any engine run on these worlds. Hash in `prereg_hash.txt`. Method: `docs/EVALUATION.md`.

## 1. Question

Can data alone teach the engine a step function, and can that knowledge then compute new results from only the
minimal new data, a new circuit or one new step, ingested and queried? Inference can't create entities
(`studies/compute`). Can a harness that creates them supply the missing part, so that engine plus harness runs
computations whose length nothing in the data fixes in advance?

## 2. Roles

- **The engine (no change)** learns the step function from examples, as tree rules. It then computes the outputs
  of each new step or circuit from its inputs.
- **The harness (`tools/harness.py`, outside the engine)** holds the tape, the head and the clock. Each step it
  creates the step's entities, ingests them, asks for the three outputs, and applies them. It stops when an output
  is missing or ambiguous, and reports that as unknown. It never fills an output in itself, and never states the
  engine's answers back as facts.

The engine contributes only the transition function, as a finite learned table. The harness contributes memory and
iteration. Any unboundedness belongs to the harness.

## 3. Settings, for every run

`TREES 1`, `DEPTH 0`, `TENDENCYSTEPS 0` (law-only proofs, after `studies/compute`).

## 4. Experiments (seeds 0-2)

- **H1, learn once, compute later.**
  - **Teach:** a knowledge base of example gates (200 each of and, or, xor; 100 not).
  - **Compute:** for each of 10 new 8-bit ripple-carry adders, ingest only its wiring and primary inputs, then ask
    for its 9 outputs.
  - **Measure:** correctness, the time for each ingest plus query, and whether the learned rules change.
- **H2, minimal data (descriptive curve).**
  - **Gates:** k example gates per kind, k = 2, 4, 8, 16, 32. Compute 10 8-bit adders and 20 multiplexers.
  - **Turing machine:** k example steps per transition, k = 1, 2, 3, 4, 6. Run the programs of H3.
- **H3, harness loop.** The machine's transitions are taught by 8 example steps each; no run is ever shown.
  - **Programs:** the 3-state busy beaver from a blank tape; binary increment on 16 inputs per seed, of 1 to 16
    bits, including all-ones inputs, where the tape grows past the input.
  - **Truth:** a plain simulator (`tools/tm.py`).
- **H4, control: an untaught transition.** Increment taught without `(carry, blank)`, then run on all-ones inputs,
  which need it, and on inputs with a zero, which don't.

## 5. Predictions (each passes or fails as written)

- **H1a.** All 30 adders (10 × 3 seeds) fully correct, and 0 wrong outputs.
- **H1b.** The learned rule set is identical before and after the 10 adders are ingested, in every seed.
- **H2.** At every k: 0 wrong answers. Too little data shows up as unanswered, not as error. The smallest k with
  every circuit, and every run, correct is reported, with no threshold.
- **H3a.** The busy beaver: the same number of steps (14), final tape and head position as the simulator, in every
  seed.
- **H3b.** Increment: final tape equal to the simulator's on all 48 inputs.
- **H3c.** The learned rule set is identical before and after each run.
- **H4.**
  - **All-ones inputs:** the harness stops with "unknown" at the step that needs `(carry, blank)`, and reports no
    final tape.
  - **Inputs with a zero:** the run completes correctly.
