# Is sharding general? Mostly not, yet, and why

Plan: `PREREGISTRATION.md` (hash in `prereg_hash.txt`). Results: `results_confirm.jsonl`; verdicts:
`results_verdicts.json` (`tools/analyze.py`). Pilot (seed 9, exploratory): `results_pilot_v1.jsonl`,
`results_pilot.jsonl`. No engine change. All sharded arms ran through `egm.shard` (consensus on, central off).

## Verdicts

| ID | Claim | Verdict |
|---|---|---|
| G1 | The automatic split reproduces one engine on every world | **FAIL**: 12 of 36 runs (company clean 6/6, lineage 6/6; company noisy, blind, gates and realcode 0/6 each) |
| G2 | The automatic split beats a random one | **PASS**: higher agreement with one engine in 12 of 12 cells |
| G3 | The automatic split is as good as the user-named one | **FAIL**: company noisy, the user-named split 6/6 identical, the automatic split 0/6 |
| G4 | It works on real data | **FAIL**: realcode 0/6 (agreement with one engine: Jaccard 0.85 at 4 shards, 0.42 at 8) |

**`egm.shard` stays experimental.** Only one world shape (the company world, with a user-named clean relation) and
one easy shape (family trees, where every rule lives inside a family) reproduce one engine.

## Results (mean of 3 seeds; Jaccard = agreement of the answer sets with one engine)

| World | One engine P / R | Automatic, 4 shards: P / R / Jaccard | Automatic, 8 shards | Random, 4 | Random, 8 | User-named, 4 / 8 |
|---|---|---|---|---|---|---|
| company, clean | 1.000 / 0.955 | 1.000 / 0.950 / 0.98 | 1.000 / 0.951 / 0.99 | 0.341 / 0.899 / 0.20 | 0.348 / 0.829 / 0.19 | identical / J 1.00 |
| company, 15% noise | 1.000 / 0.643 | 0.969 / 0.824 / 0.74 | 0.970 / 0.720 / 0.87 | 0.285 / 0.669 / 0.16 | 0.294 / 0.644 / 0.15 | identical / J 1.00 |
| blind | 0.838 / 0.519 | 0.981 / 0.489 / 0.77 | 0.982 / 0.496 / 0.79 | 0.048 / 0.505 / 0.04 | 0.968 / 0.066 / 0.10 | |
| gates (`TREES 1`) | 1.000 / 0.809 | 1.000 / 0.005 / 0.01 | 1.000 / 0.065 / 0.08 | 1.000 / 0.000 / 0.00 | 1.000 / 0.000 / 0.00 | |
| lineage (`CHAIN 3`) | 1.000 / 1.000 | identical | identical | 1.000 / 0.055 / 0.06 | 1.000 / 0.007 / 0.01 | |
| realcode (`COVERAGE 0`) | 0.016 / 0.106 | 0.017 / 0.099 / 0.85 | 0.275 / 0.097 / 0.42 | 0.020 / 0.034 / 0.25 | 0.031 / 0.018 / 0.09 | |

Notes:
- In "company, clean", the automatic split meets the match criterion but isn't identical: about 70-90 answers
  missing and 140-260 extra per run.
- Per-engine sizes and duplication are in `results_verdicts.json`. The automatic split copied 1.0-2.9× the input
  facts; it was 2.9× for blind at 8 shards.

## What went wrong, traced (exploratory analysis after the confirmatory runs)

### 1. Locality and representativeness pull in opposite directions

Two things have to hold for sharded answers to equal one engine's:
- **Locality:** inference needs every fact's evidence in the same shard (a gate with its wires, a person with their
  team).
- **Representativeness:** rule induction needs every shard to be a fair sample of every rule's evidence. Each shard
  decides on its own which rules to accept.

The automatic split (a graph partitioner) optimizes locality. It also clusters around hub values, so its shards are
skewed samples. Measured on seed 0 at 4 shards, as the share of a value's facts that sit in its largest shard (fair
is 0.25):

| Relation | Automatic | Random |
|---|---|---|
| gates `has kind` | 0.62 (one kind entirely in one shard) | 0.26 |
| company `is based in` | 0.58 (one city 94% in one shard) | 0.28 |
| blind `lives in` | 0.80 | 0.54 |

**Gates.** The skewed shards learned different, partial tree rules, and one learned a nonsense rule ("output wire
has value zero, so the gate is an AND"). Consensus then removed most answers, and recall fell to 0.005-0.065.

**Random split.** It is representative but has no locality. It separates gates from their wires (recall 0) and
families from each other (recall 0.007-0.055), and it put noise-like errors into company answers (precision 0.34).

**Why the user-named split worked on company.** It keeps teams whole (locality), and it packs teams onto shards by
load only, so every shard holds teams of every department and city (representativeness). It worked because of both
properties, not because it was named by a user.

### 2. Consensus compares rules by their text

In gates, shards learned the same rule with its branches in a different order, for example
`has first input … & has second input …` against `has second input … & has first input …`. Consensus matches rule
texts exactly, so equivalent rules counted as different and were dropped. That is a flaw in how `egm.shard`
implements consensus: it should compare rules by their logical form.

### 3. Sharding changes what is learned, not only what it costs

- **Blind world:** one engine at 38,000 facts accepted coincidence rules that most shards rejected. Sharded precision
  was 0.98 against one engine's 0.84, with lower recall.
- **Realcode at 8 shards:** consensus removed the junk rule `is defined in & imports => imports`, accepted by one
  engine, because a minority of shards accepted it. Precision went from 0.016 to 0.275.

Consensus across shards acts like a replication test (the earlier `REPLICATE` idea). That is good where it removes
junk and bad where it removes true rules learned from skewed shards (gates). Either way the answers differ from one
engine, and the match criterion counts that as failure, as it should for a tool that claims to be a drop-in
replacement.

### 4. Small defect: self-referencing facts

Facts such as `X inherits from X` (7-12 per realcode run) never enter the split graph, so no shard got them.
`egm.shard` reported them in `warnings`, as designed.

## Engine findings surfaced by the real data (not sharding; for the owner)

- **Default settings fail on real code.** With 65,000 stated facts from 125 Python packages, one engine passed the
  18 GB guard. Cause: the coverage estimate is 1-5% on code, and reliability scaled by it labels rules that agree
  1-20% of the time as law ("calls is symmetric", "calls is transitive", "imports is transitive"). Their closures
  explode. This is the same flaw the owner's lab recorded on Django.
- **With `COVERAGE 0`,** one engine completes (148 MB, 9 s), but its precision against the AST is 0.016. Almost all
  of it comes from one rule, `is defined in & imports => imports`: base-rate lift 0.5, yet accepted because 93% of
  the 82 cases with a known answer agree, out of 100,945.
- These point at coverage-scaled reliability and the agreement test (PCA acceptance) on sparse data. Both are core
  mechanisms, so changing them is the owner's decision.

## Corrections made along the way

**Peak memory.** The memory figures measured from inside the Python harness were inflated when an engine was smaller
than the harness (see `DEVIATIONS.md` in `studies/scaling` and `studies/shard`). The affected numbers in the docs
were re-measured and corrected, for example 144 MB, not 254 MB, per engine at 244,444 facts / 16 shards. No verdict
changed. In this study, the "one engine" memory values for small worlds have the same problem, so they aren't
reported.

## What would make sharding general (theoretical; each needs its own pre-registered test)

1. **A split that is both local and representative.**
   - Find structure on links between ordinary entities, leaving out value-like hubs (entities that are the object of
     many facts of one relation, such as kinds, values and cities).
   - Then pack the structures onto shards by load, without regard to hub values, as the user-named split did.
   - Deciding which entities are value-like from the data needs a rule that holds across worlds. That rule is the
     open question.
2. **Consensus by logical form:** compare rules after putting their premises in a canonical order.
3. **Accept that a shard is a sample.** Where one engine's own rule decisions are borderline (blind, realcode), no
   split can guarantee identical answers. The honest output is the agreement figure, which `egm.shard` could report
   by comparing with one engine on a sample.
