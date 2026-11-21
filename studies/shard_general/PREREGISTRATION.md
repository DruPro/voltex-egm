# Pre-registration: is sharding general?

Written 2026-11-21, before any confirmatory run. sha256 and time in `prereg_hash.txt`; changes go in
`DEVIATIONS.md`.

## Why

`egm.shard` was built and measured on one world shape: the company world, which has a relation the noise never
touches, and which the user must name. The owner's objection: that is an edge-case solution presented as general.
This study asks two things:

1. **Does sharding reproduce one engine across world shapes,** including real data?
2. **Can the split be derived from the data itself,** with no relation names?

## Worlds (generators in `hidden/worlds.py`; answer keys in `hidden/cache/`, never read by the split or the engines)

| World | Size | Settings (every arm) | What it stresses |
|---|---|---|---|
| company, clean | scale 16 (about 61,000 facts) | | a clean relation exists |
| company, 15% noise | scale 16 | | corrupted team and city facts |
| blind | scale 8 (about 38,000) | | laws, exceptions, conditional rules, decoys, sparse people |
| gates | 1,600 per kind (about 53,000) | `TREES 1` | tree rules need many examples per kind |
| lineage | 600 families (about 11,000) | `CHAIN 3` | 3-step chains inside families |
| realcode | 81,137 facts from 125 installed Python packages; 20% held out (about 65,000 stated) | `COVERAGE 0` | real data, AST truth |

- **Seeds:** 0, 1, 2. For realcode, the seed chooses the held-out 20%.
- **Shards:** 4 and 8.
- **Every engine** also gets `CLUSTERSTREAM 1` (same answers, less memory) and `MAXWORDS` sized to its input.

## Arms

| Arm | Split |
|---|---|
| single | one engine |
| **A** | `tools/split.py` `auto`: restreamed LDG over the graph of all facts, a reference rule, orphan repair. No relation names. |
| R | `split.random`: sha1(name) mod n; the naive control |
| U | the user-named split from `studies/shard` (`collaborates with` / `works under`); company only |

**A's constants, fixed before the pilot:**
- `SLACK` 1.05: shard capacity is 1.05 × nodes / n;
- `PASSES` 3;
- `MAJORITY` 0.5: an entity stays in its shard only if at least half its link weight is there.

**All sharded arms** run through `egm.shard` with its defaults: consensus on, central off.

## Pilot (seed 9, small sizes; exploratory; `results_pilot_v1.jsonl`, `results_pilot.jsonl`)

Two changes were made after the first pilot, and both apply to every confirmatory run:

1. **realcode runs with `COVERAGE 0`.** With defaults, one engine passed the 18 GB guard and was stopped.
   - Traced cause: the coverage estimate on code is 1-5%, and reliability scaled by it labels rules that agree
     1-20% of the time as law. Examples: "calls is symmetric", "calls is transitive", "imports is transitive". Their
     closures explode.
   - With `COVERAGE 0`, one engine completes, but its precision against the AST is 0.017, almost all from one
     accepted rule (`is defined in & imports => imports`, lift 0.5). That is an engine finding, reported separately.
     It is not a sharding effect.
2. **Orphan repair added to A** (step 5). The reference rule made low-degree entities unassigned, and 622 gate facts
   reached no engine. An unassigned entity with no assigned neighbour now goes back to its shard. No constant was
   changed.

**Pilot results after those changes** (2 shards, seed 9):
- **lineage:** A identical to one engine.
- **company clean:** A recall 0.942 against one engine's 0.958; U identical.
- **company with noise:** A precision 0.951 against 0.971; U identical.
- **blind:** A agrees with one engine at Jaccard 0.85.
- **gates (100 gates per kind per shard):** recall 0 for every split, against 0.70 for one engine.
- **realcode:** A agrees at Jaccard 0.94; R at 0.49.

## Hypotheses (confirmatory)

**Match criterion, per run, against one engine on the same world, seed and settings:** precision >= single - 0.001,
and recall >= 0.99 × single.

| ID | Claim | Pass if |
|---|---|---|
| G1 | Sharding with the automatic split reproduces one engine on every world | A meets the match criterion on all 36 runs (6 worlds × 3 seeds × 2 shard counts) |
| G2 | The automatic split is better than a random one | In each of the 12 world × shard-count cells, A's mean answer agreement with one engine (Jaccard) >= R's |
| G3 | The automatic split is as good as the user-named one where one exists | company (clean and noisy): A meets the match criterion on every run where U does |
| G4 | It works on real data | realcode: A meets the match criterion on all 6 runs |

**Expectation stated in advance.** The pilot makes G1, G3 and G4 likely to fail. A failure is the finding: it says
where sharding is and isn't general. Each failing world will be traced to a mechanism before anything else is tried,
and any follow-up is exploratory.

**Reported descriptively:**
- answer agreement (Jaccard, missing and extra against one engine);
- duplication (facts over all shards ÷ input facts);
- the share of entities assigned;
- consensus drops;
- engine seconds;
- one engine's peak memory.

## What a result means for `egm.shard`

- **G1 passes:** the automatic split can become `egm.shard`'s default (an SDK change, owner's decision), and the
  experimental label can be reconsidered.
- **G1 fails:** `egm.shard` stays experimental, and its docs list the world shapes where it failed and why.
