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
| `strict` | Admits a rule with at least 5 known cases, reliability >= 0.95 (agreement for one-value conclusions; the coverage-corrected rate otherwise), agreement at least 0.8 of the coverage estimate (several values per subject), and internal split-half replication (insufficient = rejected). |
| `tendency` | The `strict` stratum first, then every accepted rule extends it. Its answers always contain `strict`'s answers. |

Built-ins can't be changed. Clone one to start a custom policy.

**What strict does and doesn't guarantee (Round 1 confirmation, `studies/evidence_policy/CONFIRMATION.md`).** Strict's
answers are closed, nested inside tendency's, and its proofs are faithful. It is precise when the evidence can expose a
bad rule. It is not precise when a rule over-generalizes into territory where the conclusion is simply never stated
(a rule true only for a group looks like a law: use `CONDITIONS`), or when a rule floods on thin evidence (on the
Debian package data, strict was as imprecise as `TENDENCYSTEPS 0`, 0.006). Don't read strict as a precision guarantee.

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
| thresholds | `minAgreementToCoverage` | several values per subject, where a coverage estimate exists: agreement divided by the conclusion relation's estimated completeness. A true rule is near 1 whatever the coverage, so this separates incomplete data from an unreliable rule, which a fixed agreement floor can't | >= 0 | 0 |
| thresholds | `minCoverageSourceAgreement` | Round 2: coverage from a source rule whose own known-answer agreement is below this is not used, and reliability falls back to the rate (as with no estimate). Acts at admission only, so it can't undo induction's use of a bad estimate; for that use `COVSOURCE 1` (`docs/EVIDENCE.md`) | 0 to 1 | 0 |
| thresholds | `reliabilityBasis` | how the rule's reliability was obtained (`rel_basis`, `docs/EVIDENCE.md`): admit only the bases listed, from `agreement`, `inverse`, `global`, `self`, `rate`. `self` and `global` are assumptions rather than measurements | non-empty list | all five |
| thresholds | `minStability` | Round 2: share of 50 subject-bootstrap resamples on which the rule still passes acceptance (`stability` in the evidence vector). At 0.9 on tendency it raised precision in development but on no confirmation world, and cost recall there | 0 to 1 | 0 |
| validation | `required` | the rule must pass validation | true / false | false |
| validation | `method` | `internal_replication` (`split_half` is accepted as the same method) | | internal_replication |
| validation | `split` | `hash` (subject names) or `blocked` (first appearance in ingestion order) | | hash |
| validation | `minPerHalf` | fewest known answers in each half for the test to mean anything | whole number >= 0 | 5 |
| validation | `onInsufficient` | what the policy does with a rule too thin to test: `reject` or `admit`. Reported as `insufficient`, never as failed | | reject |
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
- **Weakest evidence.** Under a policy, every derived fact carries `weakest`: the lowest rule reliability on its best
  proof (`Fact.weakest`, `weakest=` on `ASK` and `INFER ALL` lines). Rank answers by it when you want the most
  dependable first.
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

## Recipes

Each recipe is a policy you create once and then name in `ask`, `infer` or `compare`. Start from a built-in with
`clone` when you want its validation settings; start from `create` when you want only what you name.

**Only measured reliability** (refuse reliability that is assumed: a rule judged against its own coverage estimate,
or against coverage borrowed from other relations). Removes confident errors that rest on an assumption and also
true laws that have nothing but themselves to vouch for them (`studies/reliability_basis`):

```
egm policy clone strict strict-measured
egm policy configure strict-measured --set thresholds.reliabilityBasis=agreement,inverse,rate
egm evidence facts.txt --policy strict-measured      # rel_basis column: why each rule is or isn't admitted
```

**Market or log data, where neighbouring records are correlated:** replicate on a chronological split, so a rule must
hold in the later half of the data as well as the earlier one.

```
egm policy create chrono --set thresholds.minSampleSize=20 --set validation.required=true --set validation.split=blocked
```

**Only exact one-value rules, no long chains:** lookups you can act on without checking.

```
egm policy create exact --set thresholds.minAgreement=0.99 --set thresholds.minSampleSize=30 \
                        --set inference.shapes=inverse,chain --set inference.maxDepth=2
```

**Ignore reliability that rests on a weak coverage source** (W1a). This also stops an inverse rule from being
judged by its own rate: the defect Round 2 found behind strict's confident errors (`studies/round2/CONFIRMATION.md`).
It hasn't been tested as a candidate; for the induction-side fix of contradicted estimates use `COVSOURCE 1`:

```
egm policy clone strict strict-covsrc
egm policy configure strict-covsrc --set thresholds.minCoverageSourceAgreement=0.5
```

**Seeing what a policy admits and why:** `egm evidence facts.txt --policy NAME` lists each rule with the stratum
that admits it (`core`, `extension`, `none`) beside its evidence. A rule a policy rejects is still learned; it just
doesn't take part in that policy's inference.

Settings and policies combine: settings change what is learned (`--set COVSOURCE=1`, `--set CONDITIONS=1`), policies
change what is used. `egm infer facts.txt --set COVSOURCE=1 --policy tendency-stab90`.

## SDK correction: `strict=True` (voltex3)

Before voltex3, `ask(..., strict=True)` (and `values`, `current`, `egm ask --strict`, `egm eval --strict`, MCP's
`strict`) filtered the legacy answers down to stated facts and law-tier inferences. That filter is not closed: a
law-tier fact can rest on a premise the filter drops (the capability suite's proof checker found such a case). Now
`strict=True` runs the query under the engine's built-in `strict` policy, whose answers are closed (every premise of a
proof is itself an answer); under another policy it keeps that policy's core stratum, closed by construction. The
frozen `strict` policy is unchanged; only the SDK's meaning of `strict=True` changed.

The old filter remains as an explicit compatibility alias, `legacy_strict=True`, until a major version. Mimic uses it,
because its programs rely on legacy voting: an untaught transition stays "unknown" there because tendency-tier paths
outvote the law path and the filter then hides the winner. Under the strict policy the law-quality generalization
answers instead. No evaluation uses `legacy_strict`. `make repro` (the published tokenomics results) is unchanged.

## Reproducibility

A result is reproducible from three things, all reported: the policy version (`name@version`; versions are never
modified), the evidence snapshot (`SNAPSHOT`, `Engine.snapshot()`), and the engine binary. Comparisons run every policy
on one snapshot and check that it didn't change.

## Engine level

The engine executes a fully specified configuration and stores no names: `POLICY APPLY <name> <version>
core.<field>=<v> ... [extension.<field>=<v> ...]`, `POLICY SHOW`, `POLICY LEGACY`. It validates every field and leaves
the policy unchanged on any error. A policy is not saved with the knowledge base: it is how inference runs, not
evidence.
