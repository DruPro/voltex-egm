# Tendency study: a user control for how much an answer may rest on tendencies

Pre-registered before any confirmatory run. Hash and time in `prereg_hash.txt`; changes go in `DEVIATIONS.md`.

## Design rule this study follows

The engine stays general: it represents and discovers associations and relations of any kind. Precision is the
user's to choose and to design for: which inferences to trust, how far to chain them, and what data to give the
engine. The engine's part is to expose evidence, tiers, proofs and limits, and to offer controls that are opt-in
and documented with their measured trade-offs. This study adds a control and measures it. It does not pick a
default.

## Motivation (exploratory, from `studies/noise`)

At 90% coverage of the hidden world, a weak tendency ("ancestor of & sibling of => parent of", agreement 0.41) was
accepted, and its conclusions fed other rules. In 2 of 3 seeds this gave 41,000-51,000 derived facts at precision
0.02, at 3% and at 15% noise alike.

## What is added (all opt-in; defaults reproduce the previous engine byte for byte)

| Addition | Layer | What it does |
|---|---|---|
| `SET TENDENCYSTEPS n` | inference | A proof may contain at most `n` tendency-tier rule steps, counted along the whole chain. `-1` (default) means no limit. `0` allows law-tier steps only. `1` lets a tendency conclusion be an answer but never a premise for another tendency step. Paths over the limit are not proposed. Needs `LABELS 1` (the default), which tiers the rules. |
| `CHAINS [ALL]` | presentation | Counts derived facts by inference round and by tendency steps in their proof; `ALL` lists each fact. |
| `SET MAXWORDS n`, `SET MAXRELATIONS n` | statistics | The two capacity caps found in the audit (12,000 words get categories; 40 relations kept), now settings, with `[LIMIT]` lines printed when a cap is hit. |

Smoke test on dev seed 99 only (hidden, coverage 0.9, noise 0.03; not reported as a result). That seed did not
cascade. With `TENDENCYSTEPS 1`, precision went 0.618 to 0.689 with no correct fact lost. With `0` it went to 0.983,
with recall 0.62 to 0.53. Separately, gates at 800 per kind: with `MAXWORDS 30000`, 1,016 correct and 0 wrong,
versus 0 before.

## Worlds and conditions (seeds 0, 1, 2)

- **hidden**: coverage {0.3, 0.5, 0.7, 0.9} x noise {0 (contradictions also 0), 0.03 (plus the world's 1%
  contradictions)}, scale 1.
- **company**: scale 1, noise {0, 0.15}.
- **law-chain worlds**, where the correct answers come from law-tier rules:
  - tree gates (`studies/trees` obs, `TREES 1`, seeds 0-4);
  - adders (`TREES 1`, `DEPTH 0`, seeds 0-4);
  - lineage (`CHAIN 3`);
  - remainders (`tests/worlds.remainders`, `DEPTH 0`);
  - harvest (`tests/worlds.harvest`, `CONDITIONS 1`).
- Conditions: `TENDENCYSTEPS` -1 (default), 1, 0.

## Hypotheses

- **T1 (gain).** In the cascade cells (hidden coverage 0.9, seeds whose default run derives more than 10,000 facts),
  `TENDENCYSTEPS 1` raises mean precision by >= 0.30.
- **T2 (no cost where the logic is law-tier).** In every law-chain world, `TENDENCYSTEPS 1` and `0` lose 0 correct
  inferences.
- **T3 (cost, descriptive).** For every hidden and company cell: precision, recall, and correct inferences lost or
  gained at 1 and 0. This is the trade-off table for users. There is no pass mark.
- **T4 (neutral default).** With every new setting at its default, the equivalence gate is 22/22 identical.
  `CHAINS` changes no other output.
- **T5 (capacity).** Gates at 800 per kind (16,000 words), `TREES 1`, seeds 0-2:
  - with the default cap, a `[LIMIT]` line is printed;
  - with `MAXWORDS 30000`, >= 95% of the hidden non-random gate outputs are recovered, with 0 wrong.
- **T6 (rebuild, descriptive plus one claim).** For company scales 1/2/4 and hidden scales 1/2/4, measure the time to
  build from the facts file (ingest, categories, relations, rules) and to `LOAD` a saved knowledge base plus answer
  one query. Claim: `LOAD` plus a first query takes <= 3 s at every tested size, so restoring a backup is a cheap way
  to undo a bad change. Full rebuild times are reported as measured.
- **T7 (redundancy in the pipeline).** On the noise study's repeated-report worlds (company and hidden; noise 0.15
  and 0.30; reports 3 and 5; seeds 0-4), compare two arms:
  - **Engine arm:** the engine's `VOTE 1` on the raw reports.
  - **Pipeline arm:** a 20-line Python majority filter run before ingestion. For relations the developer declares
    one-value (company: `is based in`, `is on`; hidden: `lives in`, `works as`, `is located in`), keep each
    subject's most-reported value. On a tie keep all tied values. Then ingest with defaults.

  Claim: the pipeline arm's precision is >= the engine arm's minus 0.005 and its recall is within 0.01, in at least
  7 of 8 cells (means over seeds). If so, redundancy handling can live in the data pipeline, where the developer
  knows which relations are one-value.

## What would change the plan

Nothing here decides a default. If T2 fails, the control has a hidden cost on law-tier logic and the documentation
must say where. If T7 fails, VOTE does something a pipeline cannot easily do, and the documentation says what.
