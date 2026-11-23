# Round 2: pre-registration

Hashed into `prereg_hash.txt` on 2026-11-23, before any confirmation run. Development is complete
(`DEVELOPMENT.md`). The harness was validated without running EGM on any confirmation data
(`confirm/validate_harness2.py`, `confirm/harness_validation.json`). Owner decisions: DESIGN section 6, all as
recommended. On 2026-11-23 the owner asked to follow through with the recommended choices: the held-out
condition variant is a candidate, and plain `CONDITIONS 1` is tested as a feature of its own (H6). Later changes
go in `DEVIATIONS.md`.

## 1. What is being tested

Whether the Round 2 candidates, frozen at commit `bf7a90a` plus the harness files in `confirm/`, generalize beyond
their development data:

| profile | settings, policy | candidate |
|---|---|---|
| `egm-default`, `egm-ts0`, `policy-strict`, `policy-tendency` | Round 1 frozen profiles | comparison |
| `r2-default`, `r2-ts0`, `r2-strict`, `r2-tendency` | the same with `COVSOURCE 1` | W1b |
| `r2-tendency-stab90` | `COVSOURCE 1`, tendency with `minStability 0.9` in both strata | W2 |
| `cond-r1` | `CONDITIONS 1` | the shipped condition feature |
| `cond-shipped` | `COVSOURCE 1`, `CONDITIONS 1` | comparison for W3 |
| `cond-holdout` | `COVSOURCE 1`, `CONDITIONS 1`, `CONDHOLDOUT 1` | W3 |
| B0, B1, B2, B3 | trivial baselines and AMIE (sealed worlds only) | reported, no criterion |

`minCoverageSourceAgreement` (W1a) is not a candidate: development showed it cannot reach the fault. It stays a
reported field.

## 2. Data

- **Sealed:** `studies/sealed2/gen_sealed2.py`, written by a separate agent from `studies/sealed2/SPEC.md`. All ten
  structures at default parameters, seeds 2000 to 2004. The author self-checked seeds 0 to 2. The harness check
  used seed 0 with planted engines only.
- **Real:** `confirm/realdata2.py` sets `c_headers`, `timezones`, `services` and `py_requires`, splits 2000 to 2004
  (`confirm/REALDATA.md`).
- **Not used:** any development world, dpkg, Unicode, the Round 1 Python sets.

## 3. Definitions

- Metrics are from `studies/capability/tools/metrics.py`, against complete truth. The only change since Round 1 is
  that an `[rel, subj, obj]` undeterminable key counts as answered when that exact fact is asserted.
- "mean" and "sd" are over the five seeds of a structure or set. A metric that is undefined (nothing derived) is
  left out of the mean. Where all five are undefined, the profile has *abstained* there.
- **Tolerance** for a no-harm comparison of profile P against comparison Q on metric m: `max(2·sd_Q, 0.01)`.
  For AURC the floor is 0.005 (owner decision 5).
- **Structures:** the nine with rules. `control_degree` is the control and is judged only under H8.

## 4. Hypotheses and pass criteria

| ID | Hypothesis | Pass |
|---|---|---|
| H1 | **W1b does no harm.** `COVSOURCE 1` costs nothing measurable. | For each pair (`egm-default`/`r2-default`, `egm-ts0`/`r2-ts0`, `policy-strict`/`r2-strict`, `policy-tendency`/`r2-tendency`), on every structure and real set: r2 precision ≥ Round 1 precision − tolerance (unless r2 abstains), and r2 recall ≥ Round 1 recall − tolerance. |
| H2 | **C-H1 without the equality loophole.** The Round 2 dial improves the risk-coverage curve. | At least one of `r2-default`, `r2-strict`, `r2-tendency` and `r2-tendency-stab90` has mean AURC lower than its comparison (stab90 → `policy-tendency`) by more than max(2·sd, 0.005) on at least one structure. None is higher by more than max(2·sd, 0.005) on any structure. |
| H3 | **C-H2 retest.** Strict is precise and still answers. | `r2-strict` precision ≥ 0.95 wherever it answers, on every structure and real set. It answers on at least 7 of the 9 structures. Recall ≥ `r2-ts0` recall − tolerance on every structure. |
| H4 | **W2 is a precision dial.** | `r2-tendency-stab90` precision ≥ `r2-tendency` precision − 0.005 on every structure and real set where both answer. It is higher by more than 0.005 on at least 3 of them. |
| H5 | **W3: held-out conditions recover a rare condition and cost nothing.** | On `conditional_rare`, `cond-holdout` mean precision ≥ 0.95 and recall ≥ 0.8. On every structure and real set, its precision and recall are ≥ `cond-shipped` − tolerance. |
| H6 | **`CONDITIONS 1` as a feature.** | On `conditional_rare`, `cond-r1` mean precision ≥ 0.95 and recall ≥ 0.8. On every other structure and real set, its precision and recall are ≥ `egm-default` − tolerance. |
| H7 | **Nesting.** | `r2-strict` ⊆ `r2-tendency`: 0 answers in the stricter set and not the looser one, on every world. |
| H8 | **Controls.** | On `control_degree`, 0 new facts for every EGM profile. Invented unseen-entity facts = 0 everywhere. |
| H9 | **Proofs.** | `proofs_invalid` = 0 for every EGM profile everywhere. Counterfactual test (20 per world, `r2-strict` and `r2-tendency`, sealed): 0 FAIL. |
| K-H0 | **Compatibility.** | Gate 221/221 identical against the pre-voltex3 binary, and the 91 unit tests and 30 kit checks pass. The stress bench is not re-run (declared here: it needs `/usr/bin/time`, Round 1 D3). |

Reported without criteria: rule-ranking diagnostics against `rule_quality`; the `stab90 ⊆ tendency` nesting
count, which the closure does not guarantee (one violation in the dry run); baselines; wall-clock time; the
conditions learned per profile.

## 5. Decisions the results feed (fixed now)

- **H1 passes:** `COVSOURCE 1` is recommended as the default for the next release. It stays opt-in until the owner
  decides.
- **H1 fails:** it stays opt-in, and the failures are published.
- **H4 passes:** `tendency-stab90` is offered as an example policy, not a built-in.
- **H5 and H6:**
  - Both pass: `CONDITIONS 1` is recommended as the default, with `CONDHOLDOUT` as the stricter option.
  - Only H6 passes: `CONDITIONS 1` is recommended and `CONDHOLDOUT` stays experimental.
  - Only H5 passes: the reverse.
  - Neither passes: both stay opt-in.
- **Any H7, H8, H9 or K-H0 failure** blocks every recommendation that depends on it.

## 6. Procedure

`confirm/confirm2.py sealed`, then `confirm/confirm2.py real`, then the gate and `make test`, then
`confirm/confirm2_report.py` writes `RESULTS.md` from the result files. The report applies the criteria above
mechanically. No result is re-run except after a crash, which is logged in `DEVIATIONS.md`.
