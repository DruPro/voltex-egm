# The evidence vector: what EGM knows about each rule

Every rule EGM learns carries an evidence vector: counts and statistics from the stated facts that say how well the
rule is supported. Policies (`docs/POLICIES.md`) decide which rules take part in inference by reading this vector.
This guide explains each field, how to see it, and how to read it. Status: voltex3, experimental.

## Seeing it

Engine: `RULES EVIDENCE` lists accepted rules; `RULES EVIDENCE ALL` includes rejected candidates.

```
EVIDENCE  ACCEPT  [? is in section ?](a,b) & ... => [? is in section ?](a,c)  n=5621  e+=3340  e-=2281  e?=0
          agree=0.5942  lift=...  z=...  base=...  cov=-1.0000  rel=0.5942  tier=tendency  one_value=1
          validation=internal_replication/hash:pass  admit=core  cov_source=none  cov_source_agree=undef  stability=1.00
```

SDK:

```python
import egm
with egm.Engine() as e:
    e.ingest_many(lines)
    for r in e.evidence():                    # include_rejected=True for every candidate
        print(r["rule"], r["agree"], r["rel"], r["stability"], r["cov_source"])
```

CLI: `egm evidence KB [--all] [--policy NAME] [--json]` prints the same fields as a table; `egm policy compare` shows how policies differ in their answers.

## Fields

| Field | Meaning | Read it as |
|---|---|---|
| `n` | chains: times the rule's premises hold in the stated facts | how often the rule fires |
| `e+` | the rule's conclusion is stated | confirmations |
| `e-` | the subject has a known, different value (one-value conclusions only) | contradictions; 0 for relations with several values per subject, where a missing value is unknown, not opposing |
| `e?` | the subject's answer is unknown | cases the data can't judge |
| `agree` | `e+ / (e+ + e-)` where the answer is known; `undef` if never known | known-answer agreement |
| `lift` | the rule's rate over the conclusion's base rate | how much better than chance |
| `z` | agreement above chance, in standard deviations | strength of the signal, given sample size |
| `cov` | estimated completeness of the conclusion relation (`-1` = no estimate) | see "Coverage" below |
| `rel` | reliability: the agreement for one-value conclusions, `rate / cov` (capped at 1) otherwise | the engine's own estimate of precision |
| `tier` | `law` (`rel` ≥ 0.95) or `tendency` under legacy; `core` / `extension` under a policy | the label answers carry |
| `one_value` | the conclusion relation has one value per subject (≥ 95% of subjects) | which reliability formula applies |
| `validation` | `<method>:pass`, `fail`, `insufficient` or `not_run` | an evaluation of the current evidence, never a stored property |
| `admit` | which stratum of the active policy admits it: `core`, `extension`, `none` (`-` under legacy) | |
| `cov_source` | where `cov` came from: `inverse`, `global`, `refuted`, `global_refuted`, `none` | Round 2 |
| `cov_source_agree` | the known-answer agreement of the rule that supplied `cov` | Round 2 |
| `stability` | share of 50 subject-bootstrap resamples on which the rule still passes acceptance | Round 2 |
| `cond_in`, `cond_out`, `cond_z` | conditional rules: subjects and chains inside and outside the condition, and the test statistic | |

## Coverage, and when not to trust it

For relations with several values per subject, a true rule's rate is limited by how much of the conclusion relation
was observed: if a third of `depends on` is stated, even a perfect rule is confirmed a third of the time. EGM
estimates this coverage from an inverse rule (`A(a,b) => B(b,a)` with lift ≥ 20 and ≥ 10 confirmations), which it
assumes is a law; relations without one use the median of the others (`global`). Dividing by coverage turns a rate
into a reliability, and the acceptance bar is relaxed to `0.8 × cov`.

That assumption can fail. On the Debian package data the only inverse for `depends on` was the reversed, weak
`recommends(a,b) => depends on(b,a)` (agreement about 0.2). It gave a coverage of about 0.1, which made every rule
concluding `depends on` look perfect and flooded the answers in two of five data splits (`studies/round2/DESIGN.md`).

`cov_source` and `cov_source_agree` show where an estimate came from and how good its source is. The setting
`COVSOURCE 1` (experimental) makes the engine refuse an estimate the evidence contradicts: if any other rule
concluding the relation is confirmed significantly more often (z > 3) than `cov / 0.8` allows, the estimate is
`refuted` and not used, and it does not enter the median. A relation that is c complete can't confirm a rule more
often than c; 0.8 is the tolerance acceptance already uses. On development data this removed the dpkg flood
(precision 0.52 → 0.86) and changed nothing on any synthetic world.

**Reading it:** a rule with `rel` near 1 but `agree` far below `cov`... check `cov_source`. `rel` of 1.00 from a
`global` or low-agreement `inverse` source is an assumption, not evidence.

## Stability

`stability` resamples the rule's head subjects 50 times (with replacement, seeded from the rule's text, so it is
deterministic) and re-applies the shipped acceptance test, holding the base rate and the coverage estimate fixed. A
rule accepted on 0.4 of resamples is sitting on the acceptance threshold; one at 1.0 is not.

It measures the sampling variation of the rule's own counts, not of the estimator: the dpkg flood rule has stability
1.0, because given the (bad) coverage estimate it passes on every resample. Use `COVSOURCE` for that fault and
`stability` for borderline rules. As a policy threshold (`minStability`), 0.9 raised the tendency policy's precision
on noisy and incomplete development worlds (hidden-cov70: 0.919 → 0.973) at a small recall cost; see
`studies/round2/RESULTS.md` for the confirmation.

## Validation

`internal_replication` splits the rule's head subjects in two (`hash`: by name; `blocked`: by first appearance in
ingestion order, for data where neighbouring records are correlated, such as market data) and requires the
known-answer agreement to be above chance in each half. `insufficient` means fewer than `minPerHalf` known answers
in a half: the test can't say, which is not the same as failing. It is internal: both halves come from the same
source, so it can't detect a bias the source shares. Independent-source validation is designed (Investigation V)
and not built.

## Conditions

With `CONDITIONS 1`, an accepted rule can be restricted to a group of subjects (`... if [works as](a, farmer|miner)`)
when its conclusion is missing outside the group much more than inside. `CONDHOLDOUT 1` (experimental) proposes the
condition on one half of the subjects and accepts it only if it passes on the other half, corrected for the number of
candidates tried. It removes proxy conditions (a correlated attribute that isn't the cause) at the cost of conditions
that rest on very few subjects. See `docs/SETTINGS.md` and the Round 2 results.
