# Round 2: what the confirmation decided

The criteria were pre-registered and hashed before the run (`PREREGISTRATION.md`, `prereg_hash.txt`). The verdicts
were applied mechanically by `confirm/confirm2_report.py`; the tables are in `RESULTS.md`, and the deviations
D1 to D4 in `DEVIATIONS.md`. Data: 10 structures × 5 seeds from the independent generator (`studies/sealed2`), and 4
real-data sets × 5 splits (`confirm/REALDATA.md`). The engine was frozen at commit `bf7a90a` and unchanged throughout.

## Verdicts

| ID | Verdict | In one line |
|---|---|---|
| H1 W1b no harm | **FAIL** | `r2-strict` and `r2-ts0` lose all of `reversed_weak`'s recall. Round 1's recall of 1.0 there came from a 400,000-fact flood at precision 0.0004. |
| H2 better risk-coverage curve | pass | on `reversed_weak` only (AURC 0.968 vs 0.996 and 0.999), and worse nowhere |
| H3 strict precise and answering | **FAIL** | strict derives 948 wrong facts on `reversed_weak`, 558 at 0.014 on `conditional_rare` and 128 at 0.0 on `c_headers`, and abstains on 4 of 9 structures |
| H4 stability is a precision dial | **FAIL** | precision was higher on none of the worlds; it only cost recall (`chain_noise` 1.0 → 0.40) |
| H5 held-out conditions | pass | `conditional_rare`: precision 1.0, recall 1.0, every seed, no harm anywhere |
| H6 `CONDITIONS 1` | pass | the same on `conditional_rare`, against 0.014 precision without it, and no harm anywhere |
| H7 nesting | pass | 0 violations |
| H8 controls | pass | 0 new facts on `control_degree`, 0 invented anywhere |
| H9 proofs | pass | 0 invalid proofs; 1,370 counterfactual tests, 0 FAIL |
| K-H0 legacy | pass | gate 221/221, 91 unit tests |

## What it means

**The coverage fix works on the fault it was built for, and the no-harm criterion was the wrong shape for that
structure.** `reversed_weak` is the dpkg-like world: a hierarchy plus a weak, reversed relation.

- Every Round 1 profile floods it with about 400,000 new facts at precision 0.0004, and that flood includes all
  180 hidden facts, hence recall 1.0.
- With `COVSOURCE 1` the default and tendency profiles derive 1,308 facts and still recover all 180: recall 1.0,
  precision 0.138, about 300 times fewer wrong answers.
- Strict and `TENDENCYSTEPS 0` with `COVSOURCE 1` keep none of the 180.

H1 counts that last point as harm, and H1 was written before the run, so H1 fails. On every other structure and every
real set, the fix changed nothing measurable. Its cost was also about 1,000 seconds less per `reversed_weak` world
(D4).

**Strict is still not a precision guarantee, for three reasons, one of them new.**

1. **An inverse rule is its own coverage source (engine defect, pre-existing).** Coverage for a relation is estimated
   from its best inverse rule, assuming that rule is a law. The rule's reliability is then its rate divided by its
   own rate, which is 1.0, whatever its agreement. On `reversed_weak` the decoy `requires(a,b) => suggests(b,a)`
   (agreement 0.14) gets reliability 1.0 and passes strict (`post/diagnose.py`).
   - `COVSOURCE` excludes the source from the refutation test, so it cannot catch this.
   - The policy field set aside in development, `minCoverageSourceAgreement`, would: the source agreement is 0.14.
   - This is probably also Round 1's "law at 0.15 agreement" in the stress study.
2. **Over-generalization.** A rule true only for a group (`conditional_rare`, 8% of subjects) looks like a law to
   every profile without conditions, strict included (precision 0.014). This was known from Round 1, and conditions
   fix it (H5, H6).
3. **The truth definition for real data.** On `c_headers`, strict derives that a typedef alias of a struct "is a"
   struct. On `services`, tendency derives that a service's alias uses its protocol. Both are true in the ordinary
   sense, but the extractors state those facts only for primary names, and the pre-registered truth is the
   extracted set (closed world, as with Round 1's dpkg). The verdicts stand as registered. The caveat is that
   these real-data precisions measure agreement with the extractor more than reasoning errors.

Strict also abstains completely on `multivalue`, `exceptions`, `competing` and `chain_noise`, where the default
profile is 0.66 to 1.0 precise: it is too strict where it is right, and not strict enough where an estimate
deceives it.

**Stability did not transfer.** In development, `minStability 0.9` raised tendency's precision on noisy and
incomplete worlds. On the confirmation worlds it raised precision on none, and on `chain_noise`, `c_headers` and
`services` it only lowered recall. Under the pre-fixed decision it is not offered as an example policy. It stays an
evidence field and a policy threshold.

**Conditions are the clearest result of the round.** On the hardest condition the generator offers (1 qualifying
category in 12, about 8% of subjects, with an irrelevant second attribute), every profile without conditions is
1.4% precise. All three condition profiles are perfect in every seed, with no proxy condition and no harm on any
other world or real set. The held-out variant matched the shipped search here. Its development cost, losing thin
conditions, did not show on these worlds. Caveat: about 8 hidden facts per seed, so recall rests on 40 facts in
all.

## Decisions (fixed in PREREGISTRATION section 5)

- **H1 failed:** `COVSOURCE` stays opt-in, and the failure is published here. Given the reading above, the owner may
  reasonably decide otherwise; that would be a new decision, not this round's.
- **H4 failed:** `tendency-stab90` is not offered as an example policy (the recipe was removed from
  `docs/POLICIES.md`).
- **H5 and H6 passed:** `CONDITIONS 1` is recommended as the default for the next release, with `CONDHOLDOUT` as the
  stricter option. Making it the default changes the legacy profile's output, so it is the owner's release
  decision, not a change this round makes. *(2026-11-23: the owner made it the default;
  `studies/cond_default/`.)*
- **H7, H8, H9 and K-H0 passed:** nothing blocks these recommendations.

## For Round 3

1. **Self-sourced coverage:** an inverse rule must not be the coverage source for its own reliability, for example
   by leaving it out, or by estimating its coverage from a different source. This is the most important defect the
   round found. It is in induction, and it is the most likely cause of strict's confident errors.
2. **Strict's shape:** too strict on many-valued and noisy structures (abstains where the default is 0.66 to 1.0
   precise), too lenient where an estimate deceives it. Reliability by relation type needs revisiting together with
   item 1.
3. **Real data with open-world truth:** sets where a derived fact can be checked against a source that states it
   (for example the C preprocessor's own include closure, or `pip`'s resolved dependency tree), so that real-data
   precision measures reasoning.
4. **Generator variation:** five of the nine structures (`reversed_weak`, `graded`, `exceptions`, `sparse`,
   `conditional_rare`) give identical counts in all five seeds, because the generator applies rates exactly. For
   them five seeds are closer to one sample with renamed entities, and the tolerance floors, not seed spread,
   decided the comparisons. The next generator should vary sizes and rates with the
   seed.
