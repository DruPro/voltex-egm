# Shared evaluation of conditions: findings and recommendation

Exploratory study. Numbers: `REPORT.md` (generated from `results/*.json`). Pre-registration: `PREREGISTRATION.md`,
hashed before any run (`prereg_hash.txt`). No deviations.

## 1. Was the shared evaluator sufficient?

Yes, for every pre-registered test (8 of 8 pass). Conditions were evaluated entirely by machinery that already
evaluates every other rule:

| Step | Mechanism | Condition-specific? |
|---|---|---|
| Describe | the evidence vector, computed on the conditional rule's in-group chains | no |
| Validate | internal replication on the conditional rule's own predictions | no |
| Admit | the policy's thresholds (the farmers rule: reliability 0.90 < 0.95, so `strict` excludes it and `tendency`'s extension admits it) | no |
| Use | the one inference implementation; proofs name the rule and its condition | no |
| Discover | the existing search (`specialize`), with its own criteria | **yes** (unchanged; see 3) |

One extension, observational: the condition's own evidence (inside versus outside the group, and a contrast z) is
now kept and shown by `RULES EVIDENCE` instead of discarded. It changes no behaviour (legacy gate 221/221 identical)
and makes a condition inspectable and graded rather than a bare gate.

## 2. Results

- **Farmers problem (S1 to S3):** under `tendency`, harvest precision 0.029 → 1.000 at the same recall (0.985).
  The learned rule is the base composition with the condition `works as ∈ {farmer, miner}`, exactly the generator's,
  in 5 of 5 seeds. Inside the group 91 to 107 of 93 to 108 subjects have known answers; outside, 0 of about 300;
  contrast z ≈ 20. Every proof names the rule and its condition.
- **Generalization (S4, S5), independent generator, unseen vocabulary:** the condition recovered with conditional
  precision 1.000 in 5 of 5 `conditional` worlds and 5 of 5 `conditional_decoy` worlds (the decoy correlated with
  62% of qualifying entities and was never chosen); no condition learned in 5 of 5 `conditional_control` worlds.
- **Vocabulary independence (S6):** renamed harvest, identical answers in 5 of 5.
- **No regression (S7), cost (S8):** every registered world and policy within 2 sd of baseline; time within 1.5x.

## 3. What the study does not show, and one failure inside a pass

- **A proxy condition.** The `hidden` world also contains a conditional harvest rule. With conditions, `tendency`'s
  harvest answers there became far more precise (seed 3: 351 answers, 48 correct → 43 answers, 39 correct; seed 4:
  168, 16 → 18, 13), but in one seed at 70% coverage the search chose `is from` instead of the job relation and gave 3
  answers, all wrong (seed 1). S7 passed because the effect is inside the tolerance; it is still a discovery error.
- **Discovery is private and in-sample.** The search proposes and judges a condition on the same data, with its own
  criteria. The shared machinery evaluates what it proposes; it does not propose. The proxy condition is what that
  costs.
- **The held-out worlds are simple:** one condition attribute, 2 qualifying values of 8, about 37 hidden conclusions
  per world. Conditions on 3+ values, on two attributes, or with noise were not tested.
- **Conditions remain all-or-nothing in inference.** Their evidence is graded and visible; admission and firing are
  per group, not weighted.

## 4. Layer attribution (from the design's failure map)

Representation: adequate. Evaluation: adequate. Inference: adequate. The remaining weakness is in induction: the
search's proposal step (the proxy condition, in-sample discovery). That is the layer to change next, not a new
evaluator.

## 5. Recommendation

1. **Make condition evaluation part of the core architecture, in the form tested:** discovery in induction, the shared
   evidence vector and validation, admission by policy (with `shapes: conditional` as the switch), one inference
   implementation. No separate condition evaluator is needed.
2. **Keep `CONDITIONS` an optional setting, off by default, for now** (owner, 2026-11-23: "it can remain a separate,
   optional configuration"). Turning it on by default is a separate decision that needs its own confirmation: the
   sealed generator's richer conditional worlds (3 values, two attributes, noise) and real data.
3. **Next study, in induction:** propose conditions on the discovery half and confirm them on the validation half
   (Round 2's data-independence decision), and test whether that removes proxy conditions such as `is from`.
