# Deviations

## 1. Round 2, after round 1 (results in `results_r1/`)

Round 1 ran as registered. H1a and H2 passed; H1b, H3a, H3b, H3c and H4 failed. Diagnosis, exploratory, on probe
name pools that are not the confirmation seeds:

- **The Turing machine learned nothing, at any k.** The tree search only considers target relations with at most
  8 distinct values (`mineTrees` in `src/voltex2.cpp`: "value-like targets only"). The registered encoding put
  every output in one relation, `has value`, with 10 values: the symbols zero, one and blank, the directions left
  and right, and the states A, B, C, carry and halt. So no output was ever a candidate target. This is an engine
  boundary, now in the capability matrix (`docs/EVALUATION.md`).
  - **Fix (data design, the same facts):** one relation per kind of value: `has symbol` (3 values), `has direction`
    (2), `has state` (5).
  - **What then happened:** next state and direction were learned exactly at 8 example steps per transition. Write
    needed more data, because "write one" is the majority value (7 of 9 transitions) and acceptance is measured
    against the base rate: 2/9 transitions exact at k = 24, 6/9 at k = 32, 9/9 at k = 64 and 100.
- **H1b failed because the engine learned something true.** After 10 adders were ingested, 2 new law-tier rules
  appeared about circuit wiring ("a gate fed by an AND gate's output is an OR gate", which is how a ripple-carry
  adder is built). No rule about values changed, and every output stayed correct. "Learn once" doesn't freeze the
  rules: the engine keeps learning from what it ingests.

`PREREGISTRATION_R2.md` fixes round 2 before it runs.
