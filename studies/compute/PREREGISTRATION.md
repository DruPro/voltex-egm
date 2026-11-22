# Can tree inference compute? Logic circuits and an unrolled universal automaton

Status: pre-registered before any engine run on these worlds. Hash in `prereg_hash.txt`. Method: `docs/EVALUATION.md`.

## 1. Capability

Expressiveness (trees) composed with inference (depth): can rules learned from example gates be applied in chains to
compute circuits the engine has never seen, up to universal gates and a bounded run of a universal cellular
automaton?

Matrix rows: "Expressiveness: trees", "Inference: depth".

## 2. Owning layers

Induction (tree rules) and inference (rounds). No engine change.

## 3. What this can and cannot show

- **Not Turing completeness.** Inference derives facts only about entities already in the data, never overwrites a
  value, and stops at a finite fixpoint. So it can't grow memory or loop without bound, and no result here could
  show Turing completeness.
- **What it can show:** bounded computation. A circuit, or an automaton unrolled to W cells × T steps, is computed
  when the data lays out the space-time grid and the engine supplies the step function, learned from examples.
- **Rule 110** is Turing complete only in the limit (unbounded cells and steps). A 16 × 16 run is a bounded slice
  of it.

## 4. Worlds (`tools/gen.py`, seeds 0-2, complete truth from a Python simulation)

| World | Taught (all values stated) | Computed (only primary inputs stated) | Hidden wires | Max gate depth |
|---|---|---|---|---|
| `nand` | 400 NAND gates | 30 XOR (4 NANDs), 30 full adders (9), 20 4-bit adders (36), all NAND only | 1,110 | 12 |
| `mixed` | 200 each of and, or, xor; 100 not (one input) | 10 8-bit ripple-carry adders, 20 2:1 multiplexers | 480 | 17 |
| `rule110` | 200 Rule 110 cell updates as 3-input gates (left, centre, right) | 60 held-out single gates; one 16-cell × 16-step automaton (periodic edges) from its first row | 300 | 15 |
| `rnd` (control) | 200 each of and, or; 200 of a kind whose output is random | 60 held-out random-kind outputs | 60 | 1 |

No truth table is ever stated.

## 5. Runs

Each world and seed under three configurations:
- `trees_depth0`: `TREES 1`, `DEPTH 0`;
- `trees_depth4`: `TREES 1`, the default depth;
- `notrees`: defaults, `TREES 0`.

## 6. Metrics

Per hidden wire value: correct, wrong or unanswered, by tier. Per circuit: all of its hidden wires correct.
Also: inference rounds against gate depth, and time.

## 7. Predictions (each passes or fails as written, per seed)

- **C1, functional completeness.** `nand`, `trees_depth0`: at least 95% of circuits fully correct, and 0 wrong
  wire values.
- **C2, depth and mixed gates, including a one-input gate.** `mixed`, `trees_depth0`: at least 95% of circuits
  fully correct, and 0 wrong.
- **C3, a 3-input rule.** `rule110`, `trees_depth0`: at least 95% of the 60 held-out single gates right, and 0
  wrong.
- **C4, unrolled universal automaton.** `rule110`, `trees_depth0`: at least 95% of the 240 automaton cells right,
  and 0 wrong.
- **C5, depth bound.** In every world, `trees_depth4` recovers no more wires than `trees_depth0`, and has 0 wrong.
- **C6, controls.**
  - `notrees` answers 0 hidden wires in every world;
  - in `rnd`, no random-kind output gets a law-tier answer.
- **C7, cost.** Every run finishes in under 120 s.
