# voltex3: evidence, policies and the research tooling

voltex3 separates what EGM learns from what it uses. The engine learns rules and records, for each one, the evidence
for it. A **policy** then decides which rules take part in inference, and every answer says which policy produced
it. The engine's earlier behaviour is the `legacy` policy and is unchanged byte for byte. Everything here is
experimental (branch `voltex3`), with results from two pre-registered research rounds.

## Components and their guides

| Component | What it's for | Guide |
|---|---|---|
| Evidence vector | per-rule counts and statistics: confirmations, contradictions, unknowns, agreement, coverage and its source, stability, validation | [EVIDENCE.md](EVIDENCE.md) |
| Policies | named, versioned inference contracts: built-ins `legacy`, `strict`, `tendency`, and your own, in the SDK and CLI | [POLICIES.md](POLICIES.md) |
| Induction settings | `COVSOURCE` (refuse a contradicted coverage estimate), `CONDITIONS` and `CONDHOLDOUT` (conditional rules, and proposing them out of sample) | [SETTINGS.md](SETTINGS.md), [EVIDENCE.md](EVIDENCE.md) |
| SDK and CLI | `Engine.evidence()`, `apply_policy`, `compare_policies`, `snapshot`; `egm evidence`, `egm policy`, `egm infer --policy`, `egm ask --policy` | [SDK.md](SDK.md), [POLICIES.md](POLICIES.md) |
| Capability suite | scoring any engine against complete truth: 13 capabilities, baselines, metamorphic and counterfactual checks | [RESEARCH_ROUNDS.md](RESEARCH_ROUNDS.md), [EVALUATION.md](EVALUATION.md) |
| Sealed generators and real data | confirmation worlds written by an independent agent; real-data sets with documented truth | [RESEARCH_ROUNDS.md](RESEARCH_ROUNDS.md) |
| Developing the engine | the pipeline, where each layer lives, the rules every change keeps, recipes | [DEVELOPING.md](DEVELOPING.md) |

## Quickstart

```
egm evidence facts.txt                                   # what was learned, and how well each rule is supported
egm infer facts.txt --policy strict                      # only rules with enough evidence that replicate
egm policy compare facts.txt legacy tendency strict      # same evidence, three policies
egm infer facts.txt --set COVSOURCE=1 --policy tendency  # with the Round 2 coverage fix
```

```python
import egm
with egm.open("facts.txt", settings={"COVSOURCE": 1}) as kb:
    for f in kb.infer_all(policy="strict"):
        print(f.fact, f.tier, f.policy)                  # tier: core | extension; policy: strict@builtin-1
    for row in kb.compare_policies(["tendency", "strict"]).summary:
        print(row)                                       # derived, core, extension, rules admitted per stratum
```

## Choosing

- **You want answers you can act on without checking:** `strict`, and read its limits in POLICIES.md and
  EVIDENCE.md: it is not a precision guarantee (Round 2 found an inverse rule judged by its own rate). Add
  `COVSOURCE 1` on dependency-like data with several values per subject; it removed floods on dpkg and its
  synthetic twin.
- **You want everything the data supports, labelled:** `tendency`. Answers from rules that only pass the looser
  stratum are labelled `extension`.
- **Your data has groups with different behaviour:** conditions are on by default since Round 2's confirmation
  (perfect on a condition held by 8% of subjects, where everything without it was 1.4% precise; no harm elsewhere).
  `CONDHOLDOUT 1` is the stricter variant; `SET CONDITIONS 0` turns them off. Check the conditions it learns with `egm evidence` (a rule with `if ...`).
- **You want a stricter trade than the built-ins:** clone one and set thresholds (POLICIES.md, Recipes).

What each choice achieved on unseen data is in `studies/round2/CONFIRMATION.md` (Round 2) and
`studies/evidence_policy/CONFIRMATION.md` (Round 1).
