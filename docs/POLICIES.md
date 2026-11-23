# Inference policies

A policy is a configurable inference contract: it says which learned rules may take part in inference and how far
inference may go. EGM ships three built-in policies and lets you define your own, through the SDK or the CLI, without
changing the engine. Policies never change the evidence: the same facts, under different policies, give different
derived answers, and every answer names the policy and version it was computed under.

Status: voltex3, experimental (`studies/evidence_policy`). The built-in values are development values until the
Round 1 confirmation runs.

## Built-in policies

| Policy | What it does |
|---|---|
| `legacy` | The engine's behaviour before policies, byte for byte. No configuration. The default. |
| `strict` | Admits a rule with at least 5 known cases, reliability >= 0.95 (agreement for one-value conclusions; the coverage-corrected rate otherwise), agreement >= 0.5, and internal split-half replication. |
| `tendency` | The `strict` stratum first, then every accepted rule extends it. Its answers always contain `strict`'s answers. |

Built-ins can't be changed. Clone one to start a custom policy.

## The configuration contract

Every field is enforced by the engine; a field the engine can't enforce isn't offered. Defaults restrict nothing.
Unknown fields and out-of-range values are errors, never ignored.

| Section | Field | Meaning | Values | Default |
|---|---|---|---|---|
| thresholds | `minSampleSize` | cases where the rule's answer is known | whole number >= 0 | 0 |
| thresholds | `minSupport` | confirming cases: the conclusion is stated (E+) | whole number >= 0 | 0 |
| thresholds | `minAgreement` | E+ / known cases | 0 to 1 | 0 |
| thresholds | `minReliability` | one-value conclusions: the agreement; several values per subject: the coverage-corrected rate | 0 to 1 | 0 |
| thresholds | `minCoverage` | estimated completeness of the conclusion relation (0 when it can't be estimated) | 0 to 1 | 0 |
| thresholds | `minZ` | agreement above chance, in standard deviations | any number | none |
| thresholds | `minLift` | rate over the conclusion's base rate | >= 0 | 0 |
| thresholds | `maxUnknownShare` | share of the rule's cases whose answer is unknown (E?) | 0 to 1 | 1 |
| validation | `required` | the rule must pass validation | true / false | false |
| validation | `method` | `internal_replication` (`split_half` is accepted as the same method) | | internal_replication |
| validation | `split` | `hash` (subject names) or `blocked` (first appearance in ingestion order) | | hash |
| inference | `maxDepth` | inference rounds for this stratum; 0 = until nothing new | whole number >= 0 | 4 |
| inference | `shapes` | derivation classes allowed: `inverse`, `chain`, `path`, `tree`, `conditional` | list | all |
| extension | `{thresholds, validation, inference}` | a second stratum that extends the first (see below) | | none |

Notes:

- **Opposing evidence** exists only in one-value relations, where a known different answer contradicts a rule. In a
  relation with several values per subject a missing conclusion is unknown, not opposing. `minAgreement` and
  `minReliability` follow this rule; `maxUnknownShare` limits how much of a rule's evidence may be unknown.
- **Validation is an evaluation, not a property of a rule.** It is recomputed from the current evidence every time,
  and reported with its method (`RULES EVIDENCE`, `Engine.evidence()`: `internal_replication/hash:pass`).
  Internal replication tests a rule on two halves of this knowledge base; it is not confirmation by independent
  sources, which is not available yet.
- **Use `split: blocked` for time-ordered or correlated data** (markets, logs). A hash split puts neighbouring,
  correlated observations in both halves, so one regime seen twice can look replicated. A blocked split divides
  subjects by when they first appear in the data: ingest the data in time order.
- **Strata.** A policy has a core stratum and, optionally, an `extension`. The core's rules run to their fixpoint
  first; the extension's rules (plus the core's) then extend it without overriding anything the core decided. So the
  policy's answers contain the core's answers, extension-derived facts are labelled `extension` (never `core`), and
  each stratum has its own `maxDepth`: a proof can therefore be longer than under `legacy`.
- **Not offered yet**, because the engine can't enforce them: evidence classes (held-out evidence isn't a class yet)
  and independent-source validation (Investigation V).

## SDK

```python
import egm

p = egm.policies.create("conservative",
        thresholds={"minAgreement": 0.9, "minSupport": 100, "minCoverage": 0.7},
        validation={"method": "internal_replication", "required": True, "split": "blocked"})
p = egm.policies.update("conservative", thresholds={"minAgreement": 0.95})   # conservative@2; @1 is kept
egm.policies.clone("strict", "my-strict")
egm.policies.export("conservative", "conservative.json")
egm.policies.import_("conservative.json", name="conservative-copy")
egm.policies.list(); egm.policies.versions("conservative"); egm.policies.get("conservative@1")

with egm.open("facts.txt") as kb:
    facts = kb.infer_all(policy="conservative")          # each Fact: fact.policy == "conservative@2", tier core|extension
    kb.ask("x is based in ?", policy="strict")
    kb.apply_policy("tendency")                          # from now on, until another policy (or "legacy")
    kb.evidence()                                        # each rule: its vector, validation result, admitting stratum
    cmp = kb.compare_policies(["tendency", "strict", "conservative"])   # same evidence snapshot for all
    kb.snapshot()                                        # identifier of the exact evidence state
```

The registry lives in `$EGM_POLICY_DIR` or `~/.egm/policies`, one JSON file per version; `egm.PolicyRegistry(path)`
opens another. Invalid configurations raise `egm.PolicyError` naming the field.

## CLI

```
egm policy list
egm policy show strict
egm policy create conservative --set thresholds.minAgreement=0.9 --set validation.required=true --set validation.split=blocked
egm policy configure conservative --set thresholds.minAgreement=0.95        # writes version 2
egm policy clone strict my-strict
egm policy versions conservative
egm policy export conservative -o conservative.json
egm policy import conservative.json --name conservative-copy
egm policy compare facts.txt tendency strict conservative [--json]
egm infer facts.txt --policy conservative [--json]
egm ask facts.txt "x is based in ?" --policy strict@builtin-1
```

`--set` takes `SECTION.FIELD=VALUE` or `extension.SECTION.FIELD=VALUE`; shapes take a comma list. The CLI calls the
same module as the SDK (`egm/policy.py`), so both validate and execute identically.

## Reproducibility

A result is reproducible from three things, all reported: the policy version (`name@version`; versions are never
modified), the evidence snapshot (`SNAPSHOT`, `Engine.snapshot()`), and the engine binary. Comparisons run every policy
on one snapshot and check that it didn't change.

## Engine level

The engine executes a fully specified configuration and stores no names: `POLICY APPLY <name> <version>
core.<field>=<v> ... [extension.<field>=<v> ...]`, `POLICY SHOW`, `POLICY LEGACY`. It validates every field and leaves
the policy unchanged on any error. A policy is not saved with the knowledge base: it is how inference runs, not
evidence.
