# Amendments experiment — pre-registration

Written before the AMEND prototype is built or run.

## Question
In v2.1, `UPDATE` is a delete-then-insert: the old value is removed from the record counts and no history is kept.
Does keeping the old value as an *amendment* (superseded, with version and kind), and letting inference use it,
make Voltex better at reasoning about changed facts, without breaking what works?

## Variants (one binary, switches)
- **V0** v2.1 `UPDATE` (baseline, the frozen v2.1 binary)
- **V1** `AMEND`, history only (EXPLAIN 0, DEPEV 0) — current state must equal V0
- **V2** V1 + EXPLAIN: a stated fact that the superseded value implied (through an accepted rule) is marked
  *stale, explained by amendment #k* when current facts derive a different value
- **V3** V2 + DEPEV: rule mining excludes only those explained-stale facts, instead of every fact of every touched subject
- **SUSPECT** (separate test): at amend time, report whether the old value is still implied by other stored facts

## World
Blind-world generator (hidden/world.py), scale 1, coverage 0.5, default noise (3% wrong, 1% contradictions), seeds 1–5.
Moves: a fraction m ∈ {1%, 5%, 15%, 30%} of observed people whose stated `lives in` value is correct move to a
settlement in a different region. Only `lives in` is amended; any stated `is from` is left as it was (stale), as in real logs.
The truth is updated: the mover's current region is the new settlement's region.

## Metrics
- M1 current residence of movers (all variants should be 100%)
- M2 current region of movers with a stale stated `is from`: the system's answer is the alternative value if it reports
  a conflict/staleness for that subject, otherwise the stated value
- M3 region accuracy of non-movers with a stated `is from` (false staleness check)
- M4 true expressible rules accepted, how many are law tier, decoy rules accepted
- M5 previous residence of movers (history question); V0 cannot answer and scores 0
- M6 SUSPECT flag rate on legitimate amendments (`lives in`, `works as`) vs implausible ones
  (`is located in` changed for a settlement; `is from` changed without a move), law-tier-only and any-tier
- Cost: wall time per run

## Decision rules
- **H0 (no regression)** With no AMEND commands the AMEND binary's output is byte-identical to v2.1 on the gate scripts,
  and V1's facts, rules and conflicts are set-identical to V0 in every run. Failure stops the experiment.
- **H1 (history)** Adopt history if M5 ≥ 99% and time overhead < 5%.
- **H2 (explained staleness)** Adopt EXPLAIN if, averaged over seeds, V2's M2 is ≥ 10 points above V0 at every move rate
  and M3 is no more than 0.5 points below V0.
- **H3 (dependent-only evidence exclusion)** Adopt DEPEV if at 15% or 30% moves V3 accepts more true rules or more
  law-tier true rules than V2 (mean over seeds) with no more decoys, and no M2/M3/M4 loss at 1% and 5%.
- **H4 (suspicion)** Adopt as an advisory message if, law-tier-only, ≥ 50% of implausible amendments are flagged and
  ≤ 5% of legitimate ones are.

Results that fail a rule are reported as failures, not re-tuned.
