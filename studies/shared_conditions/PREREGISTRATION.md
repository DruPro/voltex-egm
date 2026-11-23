# Shared evaluation of conditions: pre-registration

Hashed into `prereg_hash.txt` before any experimental run. Exploratory study (the owner's proposal); it changes no
default. Design: `DESIGN.md`.

## 1. Capability

C2 structural discovery (conditional structure), C3 deduction, C5 calibration and selectivity, with every other
capability protected. Matrix row "Expressiveness: conditions": spurious conditions from 9 cases (`multipremise` R2).

## 2. Owning layer

Induction (discovery), evaluation and policy (admission), inference (use). The experiment measures whether the shared
evaluation machinery suffices; the only engine change is observational (the condition's evidence, `DESIGN.md` 2).

## 3. Arms

Same engine binary, same tool version, same worlds and seeds:

- **Baseline:** Round 1 built-in policies (`strict`, `tendency`) and `egm-default`, `CONDITIONS 0`.
- **Experiment:** the same with `CONDITIONS 1`: conditions are discovered by the existing search and then evaluated,
  validated, admitted and used by the shared machinery.

## 4. Hypotheses

| ID | Hypothesis | Pass |
|---|---|---|
| S1 | Farmers problem: under `tendency` with conditions, the harvest world's derived facts reach precision >= 0.95 with recall >= 0.9 | mean over seeds 0-4, and every seed >= 0.9 precision |
| S2 | Structure recognised, not hardcoded: the learned rule is the base composition with the condition on the job relation and qualifying values exactly the generator's | 5 of 5 seeds |
| S3 | Condition distinguished from the relationship it qualifies: the condition's contrast shows the group known far more often than outside | cond_z >= 3 in 5 of 5 seeds; proofs name rule and condition |
| S4 | Generalization (held-out, independent generator `studies/sealed`, seeds 2000-2004): `conditional` worlds: the condition's relation and qualifying values recovered, and conditional conclusions at precision >= 0.9 | 4 of 5 seeds |
| S5 | No spurious condition: `conditional_control` (no condition): no conditional rule on the target; `conditional_decoy`: the decoy relation is not chosen | 4 of 5 seeds each |
| S6 | Vocabulary independence: harvest with every entity consistently renamed gives the same derived facts (mapped back) | Jaccard 1.0 on 5 of 5 seeds |
| S7 | No regression: on every registered world other than harvest, precision, recall and AURC of each policy with conditions stay within 2 sd (baseline seed spread) of the baseline arm | every world, every policy |
| S8 | Cost: total time per run with conditions at most 1.5x the baseline arm on every world | every world |

A result counts only if the structure was learned by the normal process (S2, S3), never because the expected answers
appear.

## 5. Failure analysis

As in `DESIGN.md` section 4: each failed hypothesis is attributed to a layer before any change is proposed.

## 6. Decision

- All pass: recommend conditions as a core part of the shared architecture (the search stays in induction; the policy
  decides admission), with `CONDITIONS` on by default proposed as a separate decision needing confirmation.
- Target passes but regression or generalization fails: conditions remain a separate optional configuration, with the
  failing layer named.
- Target fails: report the layer; no new subsystem without a further study.
