# Pre-registration: scaling audit, an exact fix for category building, incremental ingestion

Written 2026-11-21 before the confirmatory runs below. Its sha256 and time are in `prereg_hash.txt`; later changes go
in `DEVIATIONS.md`.

**The engine core is not changed.** `src/voltex2.cpp` is frozen as `lab/frozen_voltex2.cpp` (sha256 `75455ec9...c020`).
Everything is measured on a lab copy, `lab/voltex2_lab.cpp`, and adopting anything is the owner's decision.

## Done before this plan (descriptive audit)

**`results_audit_stages.jsonl`, `results_fit.json`.** The lab copy prints extra `[LAB]` lines only when `PROFILE` is
2. Company, hidden and gates worlds, 2 seeds each, up to 244,444 / 38,726 / 80,065 facts. Findings:

- **The category stage (`buildClasses`) is quadratic in vocabulary:** time grows as vocabulary^2.05 to ^2.08.
  - It compares every pair of word classes and stores every pair above the threshold before joining them.
  - 67-80% of all pairs pass, because words in the same slot (names) share contexts.
  - The stored pair list was 76-99.5% of peak memory at the larger sizes: 2,048 of 2,129 MB at 122,042 company
    facts, and 16,384 of 16,474 MB at 80,065 gates facts.
- **Vocabulary grows about linearly with facts** (exponent 0.92-1.00), so peak memory grows about as facts^1.9.
- **The other stages grow more slowly:** relations facts^1.1-1.2, rule mining ^1.2-1.4, inference ^1.2-1.5.
- **Ingestion throughput falls** from about 11 to about 5 MB/s as the store grows, but ingestion is under 3% of the
  total time.
- **Gate G0** (`results_gate_G0_lab_off.json`): with the new setting off, the lab copy equals the frozen engine on
  221/221 cells: 17 datasets × 13 settings, comparing every output line except throughput, timing and RSS lines.

## The variant (frozen: `lab/voltex2_lab.cpp`, sha256 in `prereg_hash.txt`)

`SET CLUSTERSTREAM 1` (off by default; not saved with the knowledge base). In each round of `buildClasses`, a pair
above the threshold is joined at once, and a pair already in one component is skipped. Nothing is listed or sorted.

Why the categories should be identical:
- The current code computes connected components of the graph of pairs above the threshold (single linkage at a
  fixed threshold), using union-find.
- Components don't depend on the order of joins, and a pair inside one component joins nothing.
- Roots remain the smallest index in each component (`uf[max] = min`), so class ids are identical too.
- A round stops when no pair joins anything, which happens exactly when the pair list would have been empty.

## Confirmatory hypotheses

| ID | Claim | Pass if |
|---|---|---|
| E1 | The variant gives the same output on the regression set. | Gate with `CLUSTERSTREAM=1`: 221/221 cells identical to the frozen engine. |
| E2 | The variant gives the same output at scale. | Identical `RELATIONS` + `INFER ALL` + `CONFLICTS` output (same sha256 after dropping timing lines), frozen vs variant, on company scale 32 and 64 (seeds 0, 1), gates per_kind 1600 (seeds 0, 1) and hidden scale 8 (seeds 0, 1). |
| M1 | Memory. | Peak RSS with the variant <= 25% of frozen, on company scale 32 (seeds 0, 1, 2) and gates per_kind 1600 (seeds 0, 1, 2). |
| M2 | Category-stage time. | Category stage time (`[PROFILE] classes`) with the variant <= 50% of frozen, same cells as M1. |
| M3 | Total CPU. | Total CPU with the variant <= 70% of frozen, on company scale 32 (seeds 0, 1, 2). |
| I1 | One new fact with a new name costs a full rebuild. | Time to the next answer after ingesting one fact naming a new entity is >= 90% of the cold first answer's time (build + inference), with `REFRESH` 0 and 0.02, company scale 8, 16 and 32, seeds 0 and 1. |
| I2 | `REFRESH` helps only when no new word arrives. | With `REFRESH 0.02`, the next answer after one fact using only known words is <= 20% of the cold first answer's time, same cells. |
| I3 | Reopening a saved knowledge base rebuilds everything. | `LOAD` plus the first answer takes >= 90% of the cold first answer's time, same cells, `REFRESH` 0. |

**How each is measured:**
- **E2, M1-M3:** frozen and variant run one after another, alone on the machine (8 cores, 23 GB). CPU and peak RSS
  come from `wait4`; `MAXWORDS` is sized to the input as in `studies/shard`.
- **I1-I3:** wall-clock time around single SDK commands (ECHO-delimited) on the lab copy with the variant off. The cold
  first answer is the first `ASK` after `INGESTFILE`.

**Expectations stated in advance:**
- **The work stays quadratic.** The variant removes the pair list, not the comparisons: pairs whose classes are
  already joined are skipped with two `find` calls, but there are still K²/2 of them. So M2 may pass while the stage
  stays quadratic in time.
- **Inference becomes the next bottleneck.** Growth exponents with the variant on are reported descriptively.

## Exploratory

- Growth exponents with the variant on, and where the time goes afterwards.
- Any idea tried after seeing these results.

## Not in scope

Changing `src/voltex2.cpp`. If E1, E2 and M1 pass, the variant is offered to the owner as an additive, off-by-default
setting with its measured cost and gain. Making it the default is a separate decision.
