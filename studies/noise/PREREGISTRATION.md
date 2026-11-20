# Noise study: can errors recede with more data, and can tuning help without losing generality?

Pre-registered before any confirmatory run. Hash and time in `prereg_hash.txt`. Changes after this point go in `DEVIATIONS.md`.

## Question

When the input contains wrong facts, does the engine get more accurate as data accumulates? Which layer should own any
improvement? Can the engine's settings be tuned to one dataset, does that help, and can a kit make tuning easy
without changing the architecture?

## What was already known (exploratory, before this registration)

- **E0 diagnosis, run before this plan.** On the company world with 30% wrong cities, all 22 wrong inferences with
  `TREES 1` came from wrong tree rules built on decoy relations ("knows", "likes"). Seven of them also used a corrupted
  fact. Without tree rules, the 3 errors at 15% noise came from correct rules applied to corrupted facts. So there are
  two error causes in two layers: coincidence rules (induction) and wrong facts used as evidence (evidence).
- **Smoke tests on dev seed 99 only.** The three mechanisms below were shaped on seed 99, which is not used for any
  confirmatory result. VOTE's one-value test was revised twice there. First version: a relation qualified when 90% of
  subjects had a majority; it never fired at 30% noise. Second version: it fired on genuinely many-value relations
  when facts were reported once. It cut company recall from 0.64 to 0.20, and that error is why rule (a) below exists.
  The "disputed" exclusion was added after seeing that a relation which no longer looks one-value makes inference add
  every proposed value.

## Mechanisms under test (all off by default, each one switch)

| Switch | Layer | What it does |
|---|---|---|
| `REPLICATE 1` | induction | Split subjects in two halves by a hash of their name. An accepted rule stays accepted only if, in each half, its predictions from stated facts agree with the stated answer at least `SUPPORT` times and with z >= 3 above the base rate (tree rules: z >= z*, the corrected threshold that accepted them). |
| `VOTE 1` | evidence | For relations where (a) at least half the facts are reported 2+ times, and (b) fewer than 10% of multi-value subjects have two values each reported 2+ times: a value reported more often than all the subject's other values together (and at least twice) outvotes them. Outvoted facts leave the evidence and are listed in `CONFLICTS` and `ASK`. Subjects without a majority are kept, reported as disputed, and ignored by inference's one-value test. |
| `QUARANTINE 1` | evidence (fed by inference) | Run inference once. Every stated fact that inference reports as a CONFLICT (two distinct rules agree on another value, the existing `CORROBORATE` rule) leaves the evidence. Rules are mined again and inference runs without it. The fact is never deleted: it is reported as a QUARANTINED conflict and in `ASK`. One round only. |
| `egm tune` (kit) | outside the engine | Chooses values for existing settings by self-supervised holdout. It changes no engine code. |

## Worlds (generator `hidden/gen.py`; the engine reads only `obs/`)

- **company**: people, teams, departments, cities; reporting lines; collaboration; decoys (`knows`, `likes`).
  Scale 1 is 40 teams (440 people). Noise replaces a person's city or team with a wrong one, independently per report.
- **hidden**: the Blind World (laws, exceptions, a conditional rule, three correlation decoys, 25 never-seen people,
  50 sparse people). Noise on `lives in`, `works as`, `is located in`.
- **gates**: xor/and/or/nand plus a random gate; noise flips stated wire values.
- **lineage**: parent facts; great-grandparent stated for 25 of 40 families (a `CHAIN 3` world).

Confirmatory seeds: 0, 1, 2 for the grids; 0-4 for VOTE. Seed 99 is the dev seed and is never reported.

## Metrics (scored against hidden truth by `tools/lib.py`)

- **precision**: new derived facts that are true / new derived facts.
- **recall**: true unstated facts recovered / true unstated facts (never-seen people excluded).
- **cause of each wrong inference**: from its proof (`ASK`). *Propagation* means a premise, or a premise's premise, is
  a corrupted stated fact. *Rule* means no premise is corrupted, so the rule itself was wrong.
- **flag hits**: corrupted stated facts reported in `CONFLICTS`.
- **invented**: derived facts about never-seen people (must be 0).
- **F0.5** = 1.25PR / (0.25P + R). Used for tuning, because precision matters more than recall here.

## Experiments and hypotheses

**E1/E2/E3 grid.** Configurations base, R, Q, RQ and the same four with `TREES 1` (T, TR, TQ, TRQ).
- company: scale {0.5, 1, 2, 4} x noise {0, 0.15, 0.30}.
- hidden: scale {1, 2, 4} x noise {0.03, 0.15, 0.30} at coverage 0.5.
- hidden coverage sweep: coverage {0.3, 0.5, 0.7, 0.9}, scale 1, noise 0.15, configurations base, R, Q, RQ.
- gates: per_kind {100, 200, 400, 800} x noise {0, 0.05, 0.15}, configurations T, TR, TQ, TRQ.

- **H1 Accumulation alone (base and T).**
  - (a) Rule errors per 1,000 new facts at the largest scale are <= those at the smallest scale, averaged over seeds,
    for every noise level > 0 on company and hidden. *Prediction: pass.*
  - (b) Propagation errors per 1,000 new facts do **not** fall by >= 50% from the smallest to the largest scale (same
    cells). *Prediction: pass*, meaning wrong facts do not recede on their own.
- **H2 REPLICATE.**
  - (a) With `TREES 1` at company noise 0.30, wrong inferences fall by >= 50% (TR vs T, summed over scales and seeds).
  - (b) On noise-free worlds, correct inferences fall by <= 5% (R vs base, TR vs T) in each world.
  - (c) With R, rule errors per 1,000 at the largest scale are <= those at the smallest scale (company and hidden,
    noise > 0).
- **H3 QUARANTINE.**
  - (a) Propagation errors fall by >= 50% (Q vs base, summed over scales and seeds) on company and hidden at noise
    0.15 and 0.30.
  - (b) Correct inferences change by <= 2% on noise-free worlds.
  - (c) Precision never falls by more than 0.5 points in any world x noise cell (mean over seeds and scales).
  - (d) Every quarantined fact appears in `CONFLICTS`.
- **E4 VOTE.** company (scale 1) and hidden (scale 1, coverage 0.5); noise {0.15, 0.30} x reports {1, 3, 5};
  configurations base, V, VQ, VRQ. For E4 the hidden world is sampled clean, then each report is corrupted.
- **H4 VOTE.**
  - (a) At reports 3 and noise 0.15, corrupted reports still used as evidence fall by >= 50% (V vs base).
  - (b) At reports 1, V's FACT and CONFLICT lines are identical to base's.
  - (c) V's precision >= base's in every cell.
  - (d) With V, errors recede with repetition: wrong inferences at reports 5 <= reports 3 <= reports 1 (mean over
    seeds), at both noise levels in both worlds.
- **E5 side effects** (descriptive, plus H5).
  - For each switch alone: the number of the 22 gate datasets whose output changes.
  - Tree gates T1 (clean, per_kind 200), lineage with `CHAIN 3`, and the harvest world with `CONDITIONS 1`: each
    switch's change in correct inferences.
  - **H5.** Invented facts about never-seen people stay 0 in every run. With every switch off, the gate is 22/22
    identical.
- **E6 tuning.** Worlds: company (0.15), company (0.30), hidden (coverage 0.5, noise 0.03), hidden (coverage 0.3,
  noise 0.15), gates (noise 0.05), lineage. Scale 1, seeds 0-2.
  - **Search space** (default first): RATE [0.4, 0.3, 0.5], LIFT [5, 3, 8], SUPPORT [3, 2, 5], PCA [0.8, 0.7, 0.9],
    COVERAGE [1, 0], CORROBORATE [1, 0], DEPTH [4, 0], CHAIN [2, 3], CONDITIONS [0, 1], TREES [0, 1],
    REPLICATE [0, 1], QUARANTINE [0, 1], VOTE [0, 1].
  - **Self-tuning.** 3 folds. Each fold hides a disjoint 15% of the stated facts (relations with >= 20 facts). The
    score is F0.5 on the hidden facts: precision counts derived facts for (relation, subject) pairs that have a hidden
    fact; recall is hidden facts recovered. Coordinate descent in the order above, at most 2 sweeps. A value is adopted
    only if it raises the mean F0.5 by >= 0.005 **and** raises it in every fold.
  - **External labels.** 10% of (relation, subject) pairs that have unstated true facts are given with their full true
    answers. Same search, single evaluation, adopt on gain >= 0.005. These pairs are excluded from the test score of
    every condition.
  - **Oracle.** The same search scored on the test truth itself: an optimistic upper bound.
  - **Test score.** F0.5 of all new derived facts against hidden truth, external-label pairs excluded.
- **H6 Tuning.**
  - (a) Self-tuned F0.5 > default on >= 4 of 6 worlds (mean over seeds), with precision never more than 1 point
    below default on any world.
  - (b) Self-tuning recovers >= 50% of the oracle's gain over default, averaged over the worlds where the oracle gains.
  - (c) Within a world, settings tuned on seed s and applied to the other seeds keep >= 50% of the gain.
  - (d) Across worlds (seed-0 settings of world A on world B, seed 1): descriptive.
  - (e) External-label tuning vs self-tuning: descriptive.
  - (f) The tuner cannot read hidden truth. It is given only the observation file. In the tuning runs a Python audit
    hook records every file it opens; none may be under `hidden/`.

## Promotion rule

A mechanism may become a default only if it passes its hypotheses **and** changes no correct inference by more than 2%
on any noise-free world. Otherwise it stays experimental (off), and its trade-off is reported. The tuning kit ships if
H6(a) and H6(f) pass.

## What would count against the whole approach

If errors do not recede with any mechanism (H1(a), H2(c) and H4(d) all fail), or if every gain comes with a loss on
noise-free worlds, the report says so: noise is then an information limit, to be labelled, not engineered away.
