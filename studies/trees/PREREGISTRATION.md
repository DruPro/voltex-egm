# Tree-shaped rules: pre-registration

Design background: DESIGN.md. Baseline: the `study/multipremise` branch at commit 5721186
(2.2.1 plus DEPTH, CHAIN, CONDITIONS and the settings registry), frozen.

## The feature: `SET TREES 1` (experimental, default 0)

**Shape.** A tree rule concludes a constant value for a subject x:

```
A(x, g)  &  branch1(g)  &  ...  &  branch_b(g)   =>   T(x, c)        (1 <= b <= 3)
```

- The anchor `A` links x to one entity g, in either direction (`A(x,g)` or `A(g,x)`).
- Each branch tests g: a **leaf** `R(g, k)` with a constant k, or a **two-step** branch
  `R(g, y) & S(y, k)` with a constant k. All entities in one match are distinct.
- `T` must be a value-like target: a one-value relation (at least 95% of subjects have one
  object) with at most 8 distinct objects. `c` is one of those objects.

**Search (evidence-guided).** For each target T and value c: describe every subject that
holds T(x, c) by the branch features of its anchors; keep features held by at least
`SUPPORT` such subjects; combine them Apriori-style into 2- and 3-branch candidates whose
every sub-combination was frequent; keep at most 300 candidates per (T, c), by support.

**Scoring.** Over every subject x with a matching anchor: n = subjects matched; k = matched
subjects with T(x, c) stated; pn = matched subjects with any T value stated; agreement =
k / pn. Base rate b_c = share of subjects with a known T value whose value is c.

**Acceptance (all required).**
1. k ≥ `SUPPORT` and pn ≥ 5 and agreement ≥ `PCA` (0.8).
2. Multiple-comparison control: z = (k − pn·b_c) / √(pn·b_c·(1 − b_c)) must exceed the
   Bonferroni-corrected threshold z* = Φ⁻¹(1 − 0.00135 / M), where M is the number of
   candidates evaluated in this build (z* = 3 when M = 1).
3. Branch economy: removing any one branch (for one-branch trees: removing the branch, so only
   the anchor remains) must lower agreement by at least 0.10. Every branch must earn its place.

No coverage correction. Reliability = agreement; law tier at ≥ `LAW` (0.95).

**Inference.** Applied every round alongside the other rules, over stated and derived facts,
with a proof listing every premise fact. Values are voted like other one-value conclusions.

## Worlds (generators in hidden/, engine sees only obs/)

- **G (gates with a decoy), 5 seeds.** 1,000 gates: 200 each of xor, and, or, nand, and a decoy
  kind `rnd` whose output is random. Two random inputs each. Output values given for two
  thirds of the gates, hidden for one third.
- **A (4-bit adders), 5 seeds.** 600 example gates (200 each of xor, and, or) fully specified,
  plus 20 ripple-carry adders built from those gate kinds (half adder for bit 0, full adders
  for bits 1–3) with only their 8 input bits given. Every internal wire and the 5 output bits
  are hidden.

## Predictions

- **T1 (G).** `TREES 0`: no gate output inferred. `TREES 1`: for xor/and/or/nand gates, at
  least 95% of hidden outputs inferred correctly and at most 1% wrong.
- **T2 (G, decoy).** No value inferred for any hidden `rnd` output, and no accepted tree has a
  branch naming `rnd`.
- **T3 (A).** `TREES 1, DEPTH 0`: at least 95% of adders have all 5 output bits correct; at most
  1% of hidden wire values wrong. Exploratory: the same at the default `DEPTH 4`.
- **T4 (no harm, hidden world, 15 runs).** `TREES 1` vs off: mean precision drops by at most
  0.01, and no run by more than 0.03; recall does not fall.
- **T5 (no harm, company world, 4 datasets).** Precision not below `TREES 0` on any dataset.
- **T6 (unchanged worlds).** Containment, remainders, divisibility, grandparent teaching: same
  correct and wrong counts as `TREES 0`.
- **T7 (cost, exploratory).** Build and inference times for G, A and the largest hidden-world
  file.
- **Gate.** `TREES 0`: byte-identical to the baseline on the 22-dataset gate.

Failures are reported as failures; changes to this plan go in DEVIATIONS.md.
