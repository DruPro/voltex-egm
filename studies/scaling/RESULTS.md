# Scaling: where the cost is, an exact fix, and incremental ingestion

The engine core (`src/voltex2.cpp`) was not changed. Everything here ran on a frozen copy
(`lab/frozen_voltex2.cpp`, identical to `src/`) and an instrumented lab copy (`lab/voltex2_lab.cpp`). Plan:
`PREREGISTRATION.md` (hash in `prereg_hash.txt`); changes: `DEVIATIONS.md`. Every number below comes from the
`results_*` files.

## Verdicts

| ID | Claim | Verdict |
|---|---|---|
| E1 | `CLUSTERSTREAM 1` gives the same output on the regression set | **PASS**: 221/221 cells identical (17 datasets × 13 settings) |
| E2 | Same output at scale | **PASS**: 10/10 large worlds identical, up to 244,444 facts (after the harness fix in DEVIATIONS 2) |
| M1 | Peak memory <= 25% of frozen | **PASS**: 6.1% (company, 122,042 facts), 1.2% (gates, 53,376) |
| M2 | Category time <= 50% of frozen | **PASS**: 14.9-16.0% (company), 18.0-18.7% (gates) |
| M3 | Total CPU <= 70% of frozen (company, 122,042) | **PASS**: 5.9 s vs 12.7 s (46-47%) |
| I1 | One fact with a new name costs a full rebuild | **PASS** (confirms a design limit): 98-105% of a cold build |
| I2 | With `REFRESH 0.02`, a fact with known words costs <= 20% of a cold build | **FAIL**: 23-36% at 30,000-122,000 facts |
| I3 | Reopening a saved knowledge base rebuilds everything | **PASS** (confirms a design limit): 102-109% of a cold build |

## 1. Where the cost is (descriptive audit)

**Data.** Company, hidden and gates worlds, 2 seeds each, sizes up to 244,444 / 38,726 / 80,065 facts
(`results_audit_stages.jsonl`, exponents in `results_fit.json`).

**The category stage dominated, and it is quadratic in vocabulary.**
- What `buildClasses` computes: single-linkage clustering of words by context. It cosine-compares every pair of word
  classes, keeps every pair above the threshold in one list, sorts it, then joins pairs with union-find.
- Names in the same slot share contexts, so 67-80% of all pairs pass. Time grows as vocabulary^2.05-2.08 and stored
  pairs as vocabulary^2.01-2.09.
- Vocabulary grows about linearly with facts, so memory grows about as facts^1.9.

| World, facts | Words clustered | Pairs kept | Pair list | Peak memory | Category share of CPU |
|---|---|---|---|---|---|
| company, 122,042 | 15,406 | 87.8 M | 2,048 MB | 2,129 MB | 61-62% |
| company, 244,444 | 30,766 | 351 M | 8,192 MB | 8,350 MB | 67-70% |
| gates, 80,065 | 48,016 | 817 M | 16,384 MB | 16,474 MB | 93-94% |

**This explains the earlier scale findings:**
- the scale study's word categories grew as facts^2.03;
- one engine ran out of address space at 244,444 facts on a 7 GB machine;
- it needed 8.35 GB here.

**Other stages grow more slowly:** relations facts^1.1-1.2, rule mining ^1.2-1.4, inference ^1.2-1.5.

**Ingestion is not the bottleneck.** Throughput fell from about 11 to 5 MB/s as the store grew, but ingesting
244,444 facts took about 1.4 s of 47 s.

## 2. An exact fix: `CLUSTERSTREAM` (lab only)

**What changes.** In each round, a pair above the threshold is joined at once, and a pair already in one component is
skipped. Nothing is listed or sorted.

**Why the result is identical:**
- Single-linkage components at a fixed threshold don't depend on the order of joins.
- A pair inside one component joins nothing.
- Roots stay the smallest index in each component, so class ids match.
- Checked: E1 on 221 cells (every setting family, including thresholds, caps, trees, chains, conditions and
  noise controls), and E2 at scale.

| Cell | CPU s, frozen → variant | Peak MB, frozen → variant | Category ms |
|---|---|---|---|
| company, 122,042 facts (3 seeds) | 12.7-12.9 → 5.9-6.0 | 2,129 → 130 | 7,751-8,150 → 1,162-1,240 |
| company, 244,444 facts (2 seeds) | 46.9-47.4 → 18.5-19.0 | 8,350 → 256 | 33,071-33,342 → 4,669-4,756 |
| gates, 53,376 facts (3 seeds) | 25.8-26.0 → 6.4-6.6 | 8,252 → 100 | 23,629-23,979 → 4,306-4,425 |
| hidden, 38,554 facts (2 seeds) | 3.4 → 2.5 | 156 → 100 | 971-983 → 103-104 |

**What it does not fix.** The comparisons are still quadratic, because a skipped pair still costs two `find` calls.
Memory drops from quadratic to linear; time drops 5-6× but keeps its quadratic shape.

**After the fix, the cost moves** (exploratory, from the same runs):
- **company:** inference 46-48% of CPU, categories 20-25%, mining 17-20%;
- **gates:** categories still 67%;
- **hidden:** mining 53%.

**For the owner:** this is an additive, off-by-default setting that gives the same answers. It is offered with these
measurements; adopting it or making it the default is your decision.

## 3. Incremental ingestion and reopening (I1-I3)

Company world, 15,000-122,000 facts, 2 seeds (`results_audit_incremental.jsonl`). Times are relative to the cold
first answer (ingest file, build, infer):

| Event | Cost of the next answer | Why (from the code) |
|---|---|---|
| One new fact naming a new entity | 98-105% | Any `INGEST` marks the model dirty. `REFRESH` applies only if no new word arrived, so everything is rebuilt. |
| One new fact with known words, `REFRESH 0` | 98-102% | Same: full rebuild. |
| One new fact with known words, `REFRESH 0.02` | 23-36% at the pre-registered sizes (23% at 122,042); 44-45% at 15,000 | Categories and rules are reused, but relations and the whole inference pass are recomputed. |
| `LOAD` a saved knowledge base, then ask | 102-109% | `SAVE` stores the evidence only (1.1 MB at 122,042 facts, written in 0.04 s, loaded in 0.25 s). The learned model is rebuilt on the first question. |

**I2 failed because inference isn't incremental.** At 122,042 facts, inference is about 22% of a cold build, so a
refreshed answer can't go below that.

## 4. Architectural limits found by reading the code

Each is listed with whether the engine reports it.

| Limit | Where | Reported? |
|---|---|---|
| Category building quadratic in vocabulary (memory and time) | `buildClasses` | No (measured here) |
| Vocabulary hard limit of 2,097,151 tokens (trigram keys pack three 21-bit ids); the process exits | `Vocab::get`, `MAX_ID` | Yes, but the process exits instead of refusing the record |
| Records with more than 8 open positions take no part in relations | `buildRelations` | No (silent) |
| A relation needs at least 3 supporting records | `buildRelations` (`best < 3`) | No (by design) |
| `MAXWORDS` 12,000 and `MAXRELATIONS` 40 | settings | Yes (`[LIMIT]`) |
| Saved knowledge bases hold evidence only; every process start rebuilds the model | `save` / `load` | Documented in a code comment |
| Every new fact means a full rebuild before the next answer; `REFRESH` covers known words only and still re-infers | `ensureModel` | No |
| `INFER` without `ALL` prints at most 10 facts with proofs; `INFER ALL` prints no rules | `inferCmd` | Partly (the help text says "with proofs") |

## 5. How to scale today, without core changes

- **Shard** (`studies/shard`). Split on a relation you know is clean, route reference facts, and keep answers whose
  rule most shards accept. This gave answers identical to one engine at up to 244,444 facts, using 254 MB per engine.
  It also sidesteps the quadratic stage, because each shard has a small vocabulary.
- **Size `MAXWORDS` to the vocabulary.** The default cap, not the engine, caused the earlier precision loss at scale.
- **Batch new facts.** A new fact costs a full rebuild, so ingest in batches and rebuild once. Use `REFRESH` only
  when updates reuse known words.
- **Keep a process alive.** Reopening a knowledge base costs a full rebuild, so serve from one long-running engine
  (the SDK and MCP server already do this) rather than starting one per query.

## 6. What would need the core (for the owner; theoretical, not measured)

1. **`CLUSTERSTREAM` as the default**, once you accept the evidence above.
2. **Fewer comparisons in category building.** Only pairs that share a context feature can reach the threshold,
   since cosine is 0 otherwise, so an inverted index over context features would find candidate pairs exactly. It
   helps when contexts are diverse. It does not help when every name shares every context (the company world).
3. **Incremental inference:** re-derive only what depends on changed facts.
4. **Save the learned model** (categories, relations, rules), so a reopened knowledge base answers without a rebuild.
5. **A rule column on `INFER ALL`**, so pipelines (consensus sharding) don't need a second session.
6. **Refuse a record when the vocabulary is full,** instead of exiting the process.

Points 3 and 4 change what a knowledge base stores, so they need their own pre-registered study with an equivalence
gate.

## Limitations

- **Synthetic worlds only.** Three synthetic worlds; no real dataset in this study.
- **Timing context:** one machine; engines run one at a time.
- **I1-I3 shape:** measured on the company world, one question shape (`ASK person is based in ?`).
- **Exploratory parts:** the post-fix stage shares in section 2 and all of section 6.

## Files

- `lab/frozen_voltex2.cpp` (copy of `src/voltex2.cpp`), `lab/voltex2_lab.cpp` (instrumentation and `CLUSTERSTREAM`).
- `tools/audit.py` (stages, incremental), `tools/fit.py`, `tools/gate.py`, `tools/compare.py`, `tools/e2_rerun.py`.
- `results_audit_stages.jsonl`, `results_fit.json`, `results_gate_G0_lab_off.json`, `results_gate_E1_stream_on.json`,
  `results_compare.jsonl`, `results_e2.jsonl`, `results_audit_incremental.jsonl`, `results_verdicts_*.json`.
- `logs/`: run output.
