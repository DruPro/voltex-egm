# Shared evaluation of conditions: design

Status (2026-11-23): exploratory study, isolated from Round 1 (whose pre-registration is hashed separately). The
owner's proposal: can conditions be evaluated by the same machinery as tendencies and structures, instead of a
condition-specific evaluator? One representation, one evaluation system, several structural forms.

## 1. Where conditions belong

Conditions are **structure, discovered by learning (induction)**, not part of a policy. A condition changes what a
rule says ("those whose job is farmer or miner harvest what their town produces"); a policy decides which rules to
trust. If a policy created conditions, policies would be judging different rule sets on the same snapshot, and
comparisons and nesting would lose their meaning. So:

| Step | Owner | Mechanism |
|---|---|---|
| Discover a condition | induction | the existing search (`specialize`, `CONDITIONS 1`) |
| Describe it | induction | the shared evidence vector, computed on the conditional rule's own chains; plus the condition's contrast (below) |
| Validate it | evaluation | the shared internal replication: the conditional rule's predictions are split and tested like any rule's |
| Admit it | policy | the same thresholds as any rule, plus the existing `inference.shapes: conditional` switch |
| Use it | inference | the one implementation (`condOK` restricts the rule to its group) |

If the experiment shows the shared machinery is insufficient or damaging, conditions remain what they are today: a
separate optional configuration (`CONDITIONS`), unchanged (owner, 2026-11-23).

## 2. What is reused, and what is extended

Reused unchanged:

- **The evidence vector.** A conditional rule's n, E+, E-, E?, agreement, lift and z are computed from its in-group
  chains (`specialize` replaces the rule's counts with the group's), so `computeEvidence` covers it.
- **Admission.** `admits()` applies the policy's thresholds to that vector; `shapes` can exclude conditional rules.
- **Validation.** Internal replication captures each rule's predictions through inference, which already honours the
  condition, so the conditional rule is replicated on its own predictions.
- **Inference and proofs.** A conditional rule fires only for subjects in its group; its proof names the rule with its
  condition.

Extended (one change, observational): **the condition's own evidence.** The search computes, for the group and for
its complement, subjects, subjects with a known answer, chains and stated conclusions, and a z for the difference.
It used to discard them. They are now kept on the rule and shown by `RULES EVIDENCE` (`cond_in`, `cond_out`,
`cond_z`). Nothing reads them, so no behaviour changes; they make a condition's support inspectable and graded
instead of a bare gate.

Not changed, and recorded as open: the search still uses its own criteria to propose a condition (group at least 3x
as often known as outside, z >= 3, conclusions almost never stated outside, at most half of the values), and
discovery is tested on the same data that proposed it. Whether those private criteria matter is what the regression
and generalization measurements below show.

## 3. Representation: a condition as an evidential relationship

A conditional rule is a pair of evidence vectors over one base rule's chains, inside and outside the group:

```
R | C       in-group chains:  n_in, E+_in, E-_in, E?_in   (the rule's own vector)
R | not C   out-group chains: n_out, E+_out, E?_out       (the condition's contrast)
cond_z      how much more often answers are known inside than outside
```

A condition is therefore graded (strong when the contrast is large and replicated, weak or inconclusive when it is
not), and contradicted when the out-group shows the conclusion stated as often as the in-group. Its admission is a
policy decision over the same fields as any rule; no condition-specific evaluator exists.

## 4. Failure analysis map

If the experiment fails, the measurements point at the layer:

| Symptom | Layer |
|---|---|
| The conditional rule is never proposed | induction: the search (representation adequate, discovery insufficient) |
| Proposed with the wrong condition, or a decoy | induction: the search's criteria |
| Proposed correctly but rejected by the policy | evaluation: admission or validation |
| Admitted but its answers are wrong or missing | inference |
| Right on harvest, wrong on held-out conditional worlds | generalization (overfit to the development world) |
| Other worlds regress | the global effect of enabling the search |
| Not identifiable from the evidence | the data, not the engine (THEORY section 7) |
