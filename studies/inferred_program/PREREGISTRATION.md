# Inferred programs: pre-registration

Status: pre-registered before the experiments run. Hash in `prereg_hash.txt`. The map of the existing
architecture is in `MAPPING.md`, with its two exploratory probes. Method: `docs/EVALUATION.md`. The engine is not
changed.

**Hypothesis.** Voltex can learn a program from examples, then execute it by repeatedly applying its learned rules
to changing state, without treating runtime state as new learning evidence.

Settings for every run: `DEPTH 0` and `TENDENCYSTEPS 0`, plus `TREES 1` for tree programs.

## Programs (taught by examples only; truth from Python)

- **P1, a finite-state machine:** count the ones in a bit string, modulo 3.
  - **States:** s0, s1, s2. **Input symbols:** b0, b1.
  - **Taught:** 64 examples of each of the 6 transitions, as one-gate steps of kind `step` (inputs: previous
    state, symbol; output: next state).
  - **Rule shape:** tree rules.
- **P2, a pointer walk:** a learned composition rule (`s at x, x next y ⇒ s then y`) over a random successor graph
  of 300 nodes, taught by 150 examples. Composition rules.
- **P3, recursion:** ancestry over parent chains of length 12. `is ancestor of` is taught on 70% of the chains, so
  the transitive rules are learned, and the rest is computed. Composition and transitive rules.
- **P4, a circuit:** 8-bit ripple-carry adders from learned and, or, xor (as in `studies/compute`). Tree rules.
- **P5, an automaton:** Rule 110, 32 cells × 16 steps, from 8 shown cases. Tree rules.

## Experiments

- **X1, execution in one pass.** Each program's runtime part is laid out in advance and computed in one inference
  pass: P1 over 64-bit strings unrolled, 20 strings; P3 the untaught chains; P4 10 adders; P5 the automaton.
  - **Measure:** correctness; that no derived fact is stated; that the rules concluding a program output are
    identical with and without the runtime part present (learned from the examples alone vs examples + runtime);
    and that one full build was done.
- **X2, execution across passes without relearning (today's `REFRESH` path).** P2 runs a walk of 200 steps, and P1
  a stepwise loop over 64 symbols. Each step replaces the state facts with `RETRACT` and `INGEST`, reusing existing
  names, then asks.
  - **Arms:** `REFRESH 0.05` and `REFRESH 0`.
  - **Measure:** correctness; full builds and refresh builds per step (from `PROFILE` lines); time per step.
- **X3, the gap: tree programs.** P1 in the X2 loop with `REFRESH 0.05`, against chunked unrolling: K steps laid out
  per pass, the last state carried into the next pass, K = 1, 8, 32 and 256, over 256 symbols.
  - **Measure:** full builds per step, and time per step.
- **X4, provenance.** For every answer in X1 and X2, check:
  - (a) its derivation reaches stated facts (the engine's proof);
  - (b) every rule used can be traced to the taught examples that support it, recovered by matching the rule
    against the taught facts outside the engine;
  - (c) that recovered support count equals the engine's own count for the rule (`k`).
- **X5, failure.** Each case is checked for a wrong law-tier output:
  - (a) P1 run on a string containing a symbol never taught (b2);
  - (b) P1 taught with one transition given mixed outputs (32 examples each way);
  - (c) P1 started in a state never taught (s3).

## Predictions

- **H1.** X1: every program's results are correct, no derived fact is ever stated, there is exactly one full build,
  and the output rules are identical with and without the runtime part.
- **H2.** X2, `REFRESH 0.05`: both P2 and P1 are correct at every step. P2 has 1 full build in total and a refresh
  build at every later step.
- **H3.** X2/X3: P1 (tree rules) takes a full build at every step even with `REFRESH 0.05` (the gate). Its time per
  step is at least 3× P2's.
- **H4.** X3: time per step falls as K rises. K = 256 is at least 10× cheaper per step than K = 1.
- **H5.** X4: (a) and (b) hold for every answer, and (c) for every rule used.
- **H6.** X5: no wrong law-tier output in any case. The run stops with unknown at the first undecidable step in (a)
  and (c); (b) leaves the mixed transition without a law-tier answer.

## Decision rule (fixed now)

An engine change is considered only if all three hold:
- H3 confirms that tree programs relearn on every state change;
- the external alternatives (one-pass unrolling, X1, and chunking, X3) can't execute unbounded computations at a
  cost comparable to the `REFRESH` path;
- the candidate change is general: domain-free and opt-in.

The candidate then is narrow: keep learned rules across small state changes for tree, path and condition rules,
as `REFRESH` already does for the others. It would go through the framework (`docs/EVALUATION.md` §7).
