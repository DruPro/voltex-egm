# Stress bench, and candidate C1 (cheaper category pair loop)

Status: pre-registered before any C1 run on the bench. Hash in `prereg_hash.txt`.

## Why a bench

Earlier infra checks used the regression gate (17 small datasets) and 3-10 large synthetic worlds. That risks tuning
the engine's cost to a few world shapes. The bench adds real code, real tables and new synthetic shapes, so a change is
judged on many use cases. The layers in `layers/` are temporary study code, not part of the engine or the SDK.

## The bench (fixed; `manifest.json` records each dataset's size and sha256)

31 datasets, each written to `obs/` by `tools/bench.py catalog`:

| Group | Datasets | Source |
|---|---|---|
| Code analysis (layer `layers/codebase.py`) | `code_py_stdlib` (275,604 lines), `code_py_dist` (400,383), `code_c_headers` (400,142), `code_js` (254,235), `code_mixed` (Python + C + JS, 930,000 lines in one engine) | the Python standard library, Debian Python packages, system C headers, public JS packages bundled with editor extensions |
| World data (layer `layers/world.py`) | `world_packages`, `world_unicode`, `world_timezones`, `world_services`, `world_mixed` | dpkg status (maintainer fields never read), Unicode 15.1 tables, tz database, /etc/services |
| New synthetic shapes (`layers/synth.py`) | zipf (and 110,893-fact big), chain, many_rel, clusters (and 79,598-fact big), phrases, messy, social | generators |
| Existing generators | company 1/8/32, company 4 with 15% noise, hidden 1/8, gates 200/2400, lineage, remainders, harvest, staff noisy | `studies/noise/hidden/gen.py`, `tests/worlds.py` |

Real sources: a seeded 20% of the facts is held out as the answer key (in `obs/keys`, never given to the engine).

Cells (`tools/bench.py cells`):
- every dataset with default settings, full script: ingest, RELATIONS, INFER ALL, CONFLICTS, CLASSES, CHAINS,
  METRICS, SAVE, LOAD, INFER ALL;
- `MAXWORDS` sized to the vocabulary when it exceeds 11,000 words;
- an update script: ingest 90%, INFER ALL, ingest 5%, INFER ALL, ingest 5%, INFER ALL, CONFLICTS;
- datasets under 40,000 facts also get TREES 1, CHAIN 3, CLASS 0.3, CLASS 0.7, DEPTH 0, COVERAGE 0, TENDENCYSTEPS 0,
  CONDITIONS 1 and MAXWORDS 300.

Each cell runs in a fresh process under `/usr/bin/time` (engine-only peak RSS), `ulimit -v` 12 GB and a 900 s timeout.
A cell that fails on either binary is "not comparable" and is reported, never counted as identical.

## Candidate C1

In the `CLUSTERSTREAM 1` path of `buildClasses`, keep i's root across the inner loop (updated when i's component
joins), use an iterative find with path compression, and skip j at once when `uf[j]` equals i's root. The same pairs
are tested in the same order with the same similarity code, and the same joins happen, so output must be identical.
The `CLUSTERSTREAM 0` path is not touched.

**Disclosed exploration (before this plan):**
- **An index over shared contexts (the literal item 2) was rejected.** 77-100% of words need the hub context to
  reach the threshold, so it would visit more pairs than now.
- **C1's loop was timed on 3 worlds**, with identical output:

  | World | Category time before → after |
  |---|---|
  | gates 2,400 | 4.6 s → 0.28 s |
  | company 32 | 0.96 s → 0.30 s |
  | realcode | 6.2 s → 1.4 s |

  `company32` and `gates2400` are also in the bench.

## Hypotheses (C1 = lab/voltex2_c1.cpp against the HEAD build)

- **H1, equivalence:** identical cleaned output on every comparable bench cell. One difference is a FAIL.
- **H2, regression gate:** `studies/scaling/tools/gate.py` gives 221/221 identical with defaults, and 221/221 with
  `CLUSTERSTREAM=0` on both binaries.
- **H3, no slowdown:** no comparable cell is slower by more than 10% + 0.3 s (single run, serial).
- **H4, speedup where categories dominate:** on the `sized|full` cells of gen_gates2400, code_mixed,
  synth_clusters_big and synth_zipf_big, total time falls by at least 1.5×.
- **H5, memory:** no comparable cell's peak RSS rises by more than 5% + 5 MB.
- **H6, tests:** `make test` and `make sanitize` pass with C1 in `src/voltex2.cpp`.

If H1, H2, H3, H5 and H6 pass, C1 replaces the loop in the core with no new setting, because it changes no output. H4
is reported either way.

## Descriptive (no verdict; for the owner)

From the base run:
- cost per dataset and script;
- the update script's time against a full build (input to item 3, incremental inference);
- precision and recall against the hidden keys per dataset and setting. Quality is the decision stack's business; it
  is reported, not tuned.
