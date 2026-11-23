# Round 2: evidence that holds up under resampling, and conditions proposed out of sample

Status (2026-11-23): **G0, design.** Category: architectural change (extends the evidence-vector contract and the
induction layer's proposal step). Method: the round framework (`studies/evidence_policy/DESIGN.md`, the framework
document) and `docs/EVALUATION.md`. Inputs: Round 1's confirmation (`studies/evidence_policy/CONFIRMATION.md`) and
the shared-conditions study (`studies/shared_conditions/FINDINGS.md`).

## 1. What Round 1 left open

| Finding | Where | Layer |
|---|---|---|
| Strict admitted flooding rules on dpkg in 2 of 5 splits (precision 0.006); acceptance is bimodal across splits | Round 1 C-H2 | induction (scoring) |
| A rule true only for a group looks like a law: missing is not false; conditions fix it, but the search proposes conditions in-sample and once chose a proxy (`is from`) | Round 1 C-H2; shared conditions | induction (proposal) |
| The ranking gain did not replicate; the sealed worlds couldn't discriminate rankings (12 of 14 perfect for every profile); C-H1 had an equality loophole | Round 1 C-H1 | evaluation |

## 2. Diagnosis of the dpkg instability (development, Round 2)

Round 1's dpkg splits are Round 2 development data. On them, the flooding rule is transitive `depends on`. Its
agreement where the answer is known is stable (0.31 to 0.35 in all five splits); its reliability `rel` is 1.0 in the
two flooding splits and about 0.33 in the others. The difference is the coverage estimate for `depends on`:

- `rescoreRules` estimates a relation's coverage from any inverse rule with lift >= 20 and at least 10 confirmations,
  assuming that inverse is a true law, and divides rates by it.
- On dpkg the only candidate is `recommends(a,b) => depends on(b,a)`: a reversed, nonsensical rule whose agreement is
  0.15 to 0.22, and whose lift sits on the threshold (22.7 and 21.8 in the flooding splits; 19.5, 18.5, 15.8 in the
  others).
- When it crosses the threshold it supplies a tiny coverage (about its own rate), which inflates `rel` to 1.0 for
  every rule concluding `depends on`.

So the instability has two causes, both in induction: **the coverage estimator trusts an unreliable source**, and
**a hard threshold turns small sampling differences into all-or-nothing changes**. This is the same mechanism as the
stress study's "law at 0.15 agreement".

## 3. The three workstreams

### W1. Evidence of the evidence: the coverage estimate's own reliability (induction, evidence vector)

The coverage component becomes evidence like any other: the vector records **which rule supplied the coverage
estimate and that rule's agreement**. A coverage estimate from an inverse rule that isn't itself reliable is not a
coverage estimate. Two options, to be measured, not assumed:

- **W1a (report only):** add `cov_source` and `cov_source_agree` to the vector; a policy field
  `minCoverageSourceAgreement` lets a policy ignore coverage from an unreliable source (rel then falls back to the
  rate, as when no estimate exists).
- **W1b (induction change, opt-in setting):** the estimator itself only uses inverse rules whose agreement passes a
  threshold. Byte-identical when off.

W1a keeps the change inside the evidence vector and the policy (the Round 1 contract); W1b changes induction. The
round measures both; the framework's principle ("fix it in the layer that owns it") favours W1b if it works, because
the estimator, not admission, is what's wrong.

### W2. Stability across resamples (evaluation, evidence vector)

Every rule gets a stability component: **the share of R resamples of the evidence on which it would be accepted**.
Resampling unit: the rule's head subjects (a subject bootstrap, deterministic seeds), so the cost is one pass of
per-subject counts per accepted rule, not R re-minings. The vector reports `stability` (0-1) and a policy field
`minStability` admits only rules accepted on at least that share. A rule accepted in 2 of 5 data splits, like the
dpkg flood, should show low stability within any one split. Limits stated up front: a subject bootstrap holds the
base rate and the coverage estimate fixed, so it measures sampling variation of the rule's own counts, not of the
estimator; whether it catches the dpkg case is a hypothesis, not an assumption.

### W3. Conditions proposed out of sample (induction)

Owner decision (Round 1, item 5): build categories on the discovery half only. The condition search proposes a
condition on the discovery half of the head subjects and it is accepted only if it passes on the validation half
(the same test, independently), with the number of candidate conditions tried corrected for (as `mineTrees` does).
Opt-in setting, byte-identical when off. Target: no proxy conditions (the `hidden` world's `is from`), held-out
conditional worlds still recovered.

### W4. An evaluation that can see ranking (evaluation)

- **A second independent generator** (a separate agent, as in Round 1) with harder structures: rules of mixed true
  reliability in one world, partial and uneven coverage, conditions on 3 values and on two attributes, conditions
  with noise, borderline (threshold-straddling) rules, dependency-like graphs with a reversed weak relation. Its seeds
  are unseen until Round 2's confirmation.
- **C-H1 without the equality loophole:** an improvement must be strict and exceed max(2 sd, an absolute floor).
- **New real data for confirmation.** dpkg, Unicode and the two Python codebases were Round 1 confirmation data and
  are Round 2 development data; Round 2's confirmation needs data the round has not seen (section 6, decision 3).

## 4. Contracts

| Piece | Layer | Contract |
|---|---|---|
| `cov_source`, `cov_source_agree` | induction → vector | which rule supplied the coverage estimate, and its agreement; -1 / none when there is no estimate |
| `minCoverageSourceAgreement` | policy | coverage from a source below it is ignored (`rel` = rate), for this policy only |
| `COVSOURCE` (W1b) | induction, setting | the estimator uses only inverse rules with agreement >= the value; 0 = off (byte-identical) |
| `stability` | evaluation → vector | share of R subject resamples on which the rule passes its acceptance test; R and seeds fixed |
| `minStability` | policy | admits only rules with stability >= the value |
| `CONDHOLDOUT` (W3) | induction, setting | conditions proposed on the discovery half, accepted only if they pass on the validation half; 0 = off |

All new fields are optional (the interface freeze), all new settings off by default, `legacy` byte-identical.

## 5. Capability claims

- **Improve:** C3 precision of strict on flooding data (dpkg) without losing recall elsewhere; C2 conditional
  structure without proxy conditions; C5 ranking, measured on worlds that can show it.
- **Protect:** everything Round 1 confirmed: nesting, no invention, proof validity and faithfulness, legacy behaviour.

## 6. Open owner decisions

1. **W1: report-and-policy (W1a), induction fix (W1b), or both measured and the better adopted?** Recommended: both
   measured; W1b preferred if equal, because the estimator owns the fault.
2. **W2 resampling unit:** subject bootstrap (cheap, recommended) or full re-mining on data subsamples (faithful to
   the dpkg splits, R times the cost)?
3. **Round 2 confirmation real data** (must be unseen by the round): recommended, from this machine, C headers
   (`/usr/include`, stress layer), time zones and services (small), and Python packages' declared dependencies
   (`Requires-Dist`, a second dependency graph); or data you supply.
4. **The second sealed generator:** a separate agent again, from a structure list alone (recommended).
5. **C-H1 floor:** the absolute AURC improvement that counts (recommended 0.005, about a quarter of the default's
   AURC on the noisy and incomplete development worlds).
