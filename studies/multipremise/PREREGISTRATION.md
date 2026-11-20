# Multi-premise study: longer chains, conditions and depth as engine options

Baseline: voltex2 2.2.1 from DruPro/voltex-egm (`src/voltex2.cpp`, sha256 6e0503a9…), frozen.
Study copy: `src/voltex2.cpp`, on local branch `study/multipremise`. Nothing is pushed.

## Questions

1. Can rules with more than two premises be learned from evidence, as an option, without
   losing what the two-premise default gives (precision, refusals, speed)?
2. Can conditional rules ("only farmers and miners harvest") be learned by specializing an
   accepted rule, without repeating the rejected representativeness check's damage?
3. Does unlimited inference depth (validated alone in the depth study) still hold when
   combined with the above?
4. (Investigation only, no hypothesis) Do these shapes reach circuit evaluation? Where
   should engine configuration live?

## Switches (all default to shipped behaviour)

- `SET DEPTH n`: inference rounds; 0 = until nothing new (default 4).
- `SET CHAIN L`: longest rule body (default 2 = shipped inverse/transitive/composition).
  For L ≥ 3, candidate path rules R1(x0,x1) & … & Rl(x(l-1),xl) ⇒ T(x0,xl), 3 ≤ l ≤ L, are
  generated only from paths that actually connect a stated T pair (evidence-guided, never by
  enumerating all relation sequences). Each is scored with the shipped statistics on distinct
  endpoint pairs: n pairs reached, k also stated in T, rate, base rate, lift, known-answer
  agreement, coverage and labels, with the shipped acceptance thresholds, unchanged.
  Inference applies them with a proof listing every premise fact.
- `SET CONDITIONS 1`: for each **accepted** rule of length ≤ 2 and each relation Q, group the
  rule's chains by the head subject's value(s) in Q. A condition set K (values of Q) is
  adopted when all hold:
  (a) within subjects having some value in K, the rule passes the shipped acceptance test;
  (b) the share of chain subjects whose answer in T is known is at least 3× higher inside K
      than outside, with a two-proportion z ≥ 3 (expected evidence is missing outside K);
  (c) outside K the rule's conclusions are stated for at most 10% of what inside K would
      predict (k_out / n_out ≤ 0.1 × k_in / n_in).
  K is built greedily from Q's values ordered by known-share, keeping values whose share is
  at least half of the best. The rule then fires only for subjects with a value in K. One
  condition per rule. Conditions never accept a rule that was rejected.

## Gate (must pass before any experiment)

G1. With all switches at default, byte-identical to the frozen baseline on the 22-dataset
    regression set. G2. Self-test passes. G3. Sanitizer build clean on the gate set.

## Hypotheses

**H1 Long chains, lineage world** (new, `hidden/gen_lineage.py`, 5 seeds). 40 five-generation
binary-tree families. Only "is parent of" plus two taught relations, each given completely for
25 families and not at all for the other 15: "is great grandparent of" (3 steps) and "is great
great grandparent of" (4 steps). No grandparent relation exists.
- H1a CHAIN 2: neither taught relation is inferred for the 15 unseen families (no expressible
  rule). Pass: 0 inferred.
- H1b CHAIN 3: great-grandparent recall on unseen families ≥ 0.95, 0 wrong; great-great not
  learned (0 inferred).
- H1c CHAIN 4: both ≥ 0.95 recall on unseen families, 0 wrong.

**H2 No harm on the hidden world** (blind world, 5 seeds × 30/50/70%, 15 runs). CHAIN 3 and
CHAIN 4 vs CHAIN 2: mean precision drops by at most 0.01; recall does not fall. Exploratory:
number of new accepted rules and how many are valid (true confidence ≥ 0.9, computed on the
hidden truth).

**H3 No harm on the company world** (clean, noisy, noisy15, noisy30). CHAIN 3/4 and CONDITIONS:
precision drops by at most 0.01 per dataset; "is based in" keeps recovering all 318 on clean.

**H4 Conditions fix the harvest failure** (blind world, 15 runs). CONDITIONS 1 vs off: wrong
"harvests" facts fall by at least 80% in total; correct "harvests" facts fall by at most 10%;
overall precision does not fall. The learned condition should be "works as ∈ {farmer, miner}".

**H5 Unchanged where nothing calls for them.** Containment world, remainders, divisibility,
grandparent teaching: CHAIN 4 + CONDITIONS 1 + DEPTH 0 give the same correct and wrong counts as
the depth study (remainders 208/225 at DEPTH 0).

**H6 Cost (exploratory).** Model build and inference time at CHAIN 2/3/4 on the largest
blind-world file; no threshold.

A failed hypothesis is reported as failed. Any change to this plan goes in DEVIATIONS.md.
