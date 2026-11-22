# Can learned rules be executed as a program? The existing architecture, mapped against the hypothesis

**Hypothesis.** Voltex can learn a program from examples, then execute it by repeatedly applying its learned rules
to changing state, without treating runtime state as new learning evidence.

This maps the engine as it is (`src/voltex2.cpp`, unchanged) against that model. It was written from the code and
from two small probes, which are disclosed as exploratory. The experiments that test it are in
`PREREGISTRATION.md`.

## The engine already has two phases

```
ensureModel()     LEARNING   categories -> relations -> rule mining   (runs only when the evidence changed: `dirty`)
ensureInferred()  EXECUTION  inferCore: apply the fixed rule list, round after round, over stated ∪ derived facts
```

- **Rule mining reads stated facts only** (`rels[i].stated`). Derived facts live in `rels[i].derived`. Inference
  rounds read both (`all(r)` = stated + derived), so a value derived in round k feeds round k+1, and is never
  counted as evidence.
- **The rule list is fixed during inference.** It changes only when `ensureModel` re-mines.
- **`ensureModel` has a second path.** When `REFRESH` is on, no new words have appeared, and the change is a small
  share of the records, it rebuilds relations and **keeps the learned classes and rules** (`remapRules`; source
  comment: "evidence changed a little: re-project and rebuild relations, keep the learned classes and rules"). The
  path is switched off when `TREES`, `CHAIN 3+`, `CONDITIONS`, `REPLICATE` or `QUARANTINE` is on.

## The questions

| Question | Status | Where it stands |
|---|---|---|
| Can the inference machinery execute an inferred program? | **Works, within one pass** | A circuit, or an automaton unrolled 16 steps, was computed in one inference pass. Each step's values were derived from the previous step's derived values (`studies/compute`). |
| Can successive rounds run over changing state without rebuilding the statistical and induction layers? | **Works for composition rules; missing for tree rules** | Within a pass, rounds never rebuild. Between passes, a state change marks the evidence `dirty`. With `REFRESH` the learned rules are kept (probe 2: a counter, 12/12 steps right, rules learned once, 0.69 ms/step). With tree, path or condition rules, `REFRESH` is off, so every change re-mines. |
| Minimum external machinery? | **A small loop** | The engine never allocates entities or overwrites a value within a pass, so something outside must (1) hold the current state, (2) replace it between passes (`RETRACT` and `INGEST`), and (3) decide when to stop. To avoid relearning, it must also reuse existing names, because a new word disables `REFRESH`. |
| Can derived results feed later inference without being promoted to evidence? | **Yes, within a pass; across passes, only if restated** | Within a pass this is the design. Between passes, the next state has to be put back as a stated fact, and today that makes it evidence unless the `REFRESH` path applies. |
| How should execution tell given inputs, derived state and learned rules apart? | **Partly there** | Every answer is labelled stated, inferred, law or tendency, with its proof, and rules are listed separately. But a runtime input and a taught example are both "stated": nothing marks runtime input as "not evidence" except the `REFRESH` path's behaviour. |
| Can a trace preserve a proof back to the original examples? | **Partly** | A derived fact's proof reaches stated facts and names the rule (`ask(...).because`, `rule`). A rule's evidence is exposed only as counts (`n`, `k`, `known`, `agree`), not as the list of examples that support it. That list can be recovered outside the engine by matching the rule against the taught facts. |
| No rule applies / rules conflict / unknown state? | **Works** | No rule: no answer. In strict mode, an answer resting on a tendency is withheld. On single-valued relations, conflicting values become votes and contradictions are reported. The harness stops on any of these (`studies/harness` H4, Mimic). |
| Recursion, state machines, circuits, more general structures? | **Within limits** | Recursive rules (transitive ancestry) reach a fixpoint (`studies/strengths`). Circuits and unrolled automata run in one pass. State machines with unbounded length need the external loop, because the state space can't be laid out in advance. |

## What is fundamentally incompatible, and what isn't

- **Compatible, by design:**
  - rules learned once and applied repeatedly;
  - derived state feeding derived state without becoming evidence;
  - proofs;
  - abstaining when no rule applies.
- **Incompatible within one pass, but not a blocker:**
  - inference is monotonic: it never overwrites a value;
  - it can't create entities.

  So time has to be explicit: either one entity per step, laid out in advance (unrolling), or a loop outside that
  replaces the state between passes. That is the same split as hardware: combinational logic (the learned rules)
  plus a clock and a register (the loop).
- **Missing, not incompatible:** keeping learned rules across a state change when the program uses tree, path or
  condition rules (the `REFRESH` gate). Also a way to mark runtime input as not evidence, other than that path.

## Probes behind this (exploratory, before the pre-registration)

1. **Mimic with `TREES`:** each step re-learned categories (72 ms) and rules (42 ms) at 12,288 taught facts, with or
   without `REFRESH` and recycled names. Reason: the `REFRESH` gate excludes `TREES`.
2. **A counter learned by composition** (`s at x, x next y ⇒ s then y`): the state is replaced each step by
   `RETRACT` and `INGEST` with existing names.
   - **Correctness:** 12/12 steps right in both modes, all law tier.
   - **With `REFRESH`:** the rules were mined once and every later step took the refresh path, at 0.69 ms per step
     against 1.57 ms with full relearning.
