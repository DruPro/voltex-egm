# Engine settings

Generated from the engine's settings registry (`CONFIG` command). Every setting is saved with a
knowledge base in `<file>.cfg` except diagnostics, and `SET` after `LOAD` overrides a saved value.

**Experimental** settings are study options: off by default, tested, but not recommended for all
data. Turning one on makes `RELATIONS` print `[CONFIG] experimental settings on: ...`.

| Setting | Default | Layer | Status | What it does |
|---|---|---|---|---|
| `MAXWORDS` | 12000 | statistics | stable | categories for this many most frequent words; rarer words are not slots |
| `MAXRELATIONS` | 40 | statistics | stable | relations kept, largest first |
| `CLASS` | 0.5 | statistics | stable | similarity needed to merge words into a category |
| `CLUSTERSTREAM` | 1 | statistics | stable | build categories without listing every similar pair: same categories and answers, far less memory (1/0; 0 = the listed-pairs path) (studies/scaling) |
| `RATE` | 0.4 | induction | stable | minimum share of chains whose conclusion is stated |
| `LIFT` | 5 | induction | stable | minimum rate over the conclusion's base rate |
| `SUPPORT` | 3 | induction | stable | minimum confirming chains for a rule |
| `PCA` | 0.8 | induction | stable | minimum agreement where the answer is known |
| `LAW` | 0.95 | induction | stable | reliability needed for the law tier |
| `COVERAGE` | 1 | induction | stable | relax the rate bar when data looks sparse (1/0) |
| `LABELS` | 1 | induction | stable | label rules and facts law or tendency (1/0) |
| `CHAIN` | 2 | induction | **experimental** | longest rule body, 2-8 premises (studies/multipremise) |
| `CONDITIONS` | 0 | induction | **experimental** | learn group conditions on accepted rules (1/0) (studies/multipremise) |
| `TREES` | 0 | induction | **experimental** | tree-shaped rules joining several branches at one entity (1/0) (studies/trees) |
| `REPLICATE` | 0 | induction | **experimental** | a rule must also hold in each half of its subjects (1/0) (studies/noise) |
| `TENDENCYSTEPS` | -1 | inference | **experimental** | most tendency-tier steps one proof may contain, -1 = no limit (studies/tendency) |
| `DEPTH` | 4 | inference | stable | inference rounds, 0 = until nothing new (studies/depth) |
| `CORROBORATE` | 1 | inference | stable | a contradiction needs two distinct rules (1/0) |
| `OBS` | 1 | evidence | stable | project the observation log (1/0) |
| `STALE` | 1 | evidence | stable | staleness checks after updates (1/0) |
| `CHGREMOVALS` | 1 | evidence | stable | only removals feed the change signal (1/0) |
| `SAMEFIX` | 1 | evidence | stable | same-rule re-derivation confirms a stale candidate (1/0) |
| `VOTE` | 0 | evidence | **experimental** | a value reported more often than all others outvotes them (1/0) (studies/noise) |
| `QUARANTINE` | 0 | evidence | **experimental** | stated facts two rules contradict stop counting as evidence (1/0) (studies/noise) |
| `DX` | 0 | evidence | **experimental** | explained staleness for observations (1/0) |
| `DECL` | 0 | evidence | **experimental** | declarative amendment records (1/0) (earlier study) |
| `DECLMINE` | 0 | evidence | **experimental** | mine amendment records as facts (1/0) (earlier study) |
| `DECLFN` | 0 | evidence | **experimental** | one-value fix for amendments (1/0) (earlier study) |
| `REFRESH` | 0 | build | **experimental** | reuse classes and rules for small changes (share of records, 0 = off) |
| `PROFILE` | 0 | diagnostics | stable | print timings (1/0) |

## The experimental options, and the evidence

- `CHAIN` (2-8): rules with more than two premises. Excellent on chain-shaped data (family trees:
  3,000 correct inferences, 0 wrong, where the default makes none). Lowers precision on
  coincidence-rich data (hidden world: 0.955 to 0.931 at 3, 0.903 at 4) and is slower. See
  `studies/multipremise/RESULTS.md`.
- `CONDITIONS` (0/1): restricts a rule to the group it actually holds for. Found the hidden
  world's true rule (only farmers and miners harvest), cut those errors 98%, best precision of
  any configuration (0.980). One spurious condition from 9 cases remains. Same study.
- `TREES` (0/1): tree-shaped rules, where several branches meet at one entity (a gate's kind and
  its inputs decide its output). Learned exact truth tables: 1,319 of 1,332 hidden gate outputs,
  0 wrong; 100 of 100 four-bit adders computed with `DEPTH 0`; nothing learned for a random gate.
  Costs precision under heavy noise (100% to 97.9% with 30% noise) and mining time on large data
  (about 9 s on the hidden world). See `studies/trees/RESULTS.md`.
- `VOTE` (0/1): for data where the same fact is reported several times by independent sources.
  A value reported more often than all the others together outvotes them; outvoted facts are
  listed in `CONFLICTS` and `ASK`, never deleted. Company world, 3 reports with 15% wrong each:
  precision 0.32 to 0.998, recall 0.80 to 0.95. Without repeated reports it changes nothing.
  In the hidden world, cleaner evidence let more tendency rules fire (precision 0.980 to 0.960
  with 5 reports). See `studies/noise/RESULTS.md`.
- `QUARANTINE` (0/1): a stated fact that two distinct rules contradict stops counting as evidence
  (it is reported, not deleted), and rules are learned again without it. Raises recall on noisy
  company data (0.72 to 0.93 at 15% noise, 1,760 people). It did not cut propagated errors as
  predicted, and with `TREES 1` at 30% noise it lowered precision (0.975 to 0.939). Same study.
- `REPLICATE` (0/1): keeps a rule only if it also passes in each half of its subjects. It removed
  70% of the wrong inferences with `TREES 1` at 30% noise, but cost 36% of the correct gate outputs with
  `TREES 1` on clean data, and real correlations replicate anyway. Not recommended. Same study.
- `TENDENCYSTEPS` (-1, or 0 and up): the most tendency-tier rule steps one proof may contain.
  `0` keeps only answers that follow from law-tier rules: precision 0.97-1.00 in every world
  tested, and it stops the high-coverage cascade (precision 0.023 to 0.975). The cost depends on
  how complete your data is: true rules whose conclusions are only partly stated count as
  tendencies, so lineage (25 of 40 families stated) and harvest lost every answer, and company
  recall fell from 0.96 to 0.50. `1` barely changes the cascade, because the cascade is one
  tendency step amplified by law rules (see `CHAINS`). Choose it for your data;
  `studies/tendency/RESULTS.md` has the full table.
- `MAXWORDS`, `MAXRELATIONS`: capacity caps. When one is hit, `RELATIONS` prints a `[LIMIT]`
  line naming the setting. At 16,000 words, raising `MAXWORDS` to 30000 took tree gates from
  0 to 3,198 of 3,198 correct outputs. Raising it makes builds slower (5 s to 9 s there).
- `DX`, `DECL`, `DECLMINE`, `DECLFN`: options from earlier studies of change handling; see `docs/papers/`.
- `REFRESH`: on a small change with no new words (net change at most this share of records), it keeps the learned
  categories and rules and re-projects the relations. It re-attaches every relation a rule references: premises,
  conclusion, path steps, the condition relation (whose subjects are recomputed) and tree branches. It applies with
  `TREES` (`studies/refresh_trees`), but not with `CHAIN 3+`, `CONDITIONS`, `REPLICATE` or `QUARANTINE`. With
  `REFRESH` off, output is byte-identical to before (gate 221/221).

`DEPTH` is stable: `SET DEPTH 0` runs inference until nothing new is derived (`studies/depth/`).

## `CLUSTERSTREAM`: large vocabularies without the memory blow-up (on by default)

**Status.** On by default since the promotion check in `studies/scaling/PROMOTION.md`. The new default gave the
previous build's output on 221 of 221 regression cells and on 3 large worlds. You don't need to set it; `SET
CLUSTERSTREAM 0` brings back the old path.

**What it does.** Category building compares every pair of word classes. The old path (`CLUSTERSTREAM 0`) first lists every pair
similar enough to merge, then merges them. In data where many words share a slot (names, ids, wires), about 70% of all pairs
qualify, so that list grows with the square of the vocabulary. It was 76-99.5% of the engine's peak memory at large
sizes. `CLUSTERSTREAM 1` merges each pair as soon as it is found and skips pairs whose words are already in one
category, so no list is kept.

**What it doesn't change.** The categories are the same, so the relations, rules, tiers, answers, proofs and conflicts
are the same. The reason: categories are the connected groups of similar pairs, which don't depend on the order pairs
are found, and class ids stay the smallest index of each group. Checked:
- byte-identical output on 221 of 221 regression cells (17 datasets × 13 settings, including `CLASS` 0.3 and 0.7,
  `MAXWORDS` caps, `TREES`, `CHAIN`, `CONDITIONS`, `VOTE`, `QUARANTINE`, `REPLICATE`, `DEPTH 0`, `TENDENCYSTEPS 0` and
  the v2.0 flags), including `SAVE` and `LOAD`;
- identical output on 10 of 10 large worlds up to 244,444 facts;
- the sanitizer build. See `studies/scaling/RESULTS.md`.

**What the old path costs.** Its pair list takes about 8-9 bytes × words² (rounded up to a power of two), on top of
everything else:

| Distinct words | Pair list without it (measured) | Peak memory without → with it | CPU without → with it |
|---|---|---|---|
| 1,966 | 32 MB | (small either way) | |
| 7,726 | 512 MB | | |
| 15,406 (122,042 company facts) | 2,048 MB | 2,129 → 130 MB | 12.7 → 5.9 s |
| 30,766 (244,444 company facts) | 8,192 MB | 8,350 → 256 MB | 47 → 19 s |
| 32,016 (53,376 gates facts) | 8,192 MB | 8,252 → 72 MB | 26 → 6.5 s |

Below about 2,000 words the two paths make no practical difference.

**When to turn it off.** Only to reproduce a timing or memory measurement made with an earlier build, because the
answers are the same either way. Set it before the first question, because categories are built on the first query
after ingesting:

```
SET CLUSTERSTREAM 0
INGESTFILE facts.txt
```

For large vocabularies, the setting to think about is `MAXWORDS`:

```python
with egm.open("facts.txt", settings={"MAXWORDS": 40000}) as e: ...
```

```
egm build facts.txt -o kb.vtx --set MAXWORDS=40000
```

**Notes:**
- **Saved with the knowledge base only when non-default:** `SET CLUSTERSTREAM 0` is written to `kb.vtx.cfg` and
  restored by `LOAD`.
- **Older engines** (2.2.1 and before) don't have the setting. They give the same answers, with the old memory use.
  A knowledge base built here opens there unchanged.
- **Pair it with `MAXWORDS`** sized to your vocabulary (distinct words plus some headroom). `MAXWORDS` decides which
  words get categories; `CLUSTERSTREAM` only makes building them cheaper. Above 12,000 words, the default cap prints
  `[LIMIT]` and costs answers. Raising the cap used to cost memory quadratically; with `CLUSTERSTREAM` on it doesn't.
- **`egm tune` doesn't search it,** because it never changes answers. Set it yourself.
- **`REFRESH`** reuses existing categories on small updates, so the setting matters only for full builds.

**What it doesn't fix:**
- **Category building time is still quadratic** in vocabulary. Each pair is still visited; pairs already in one
  category are skipped with a cheap check (made cheaper again in `studies/stress`: gates 2,400 build 22.1 s → 2.4 s,
  same output on 294 of 294 bench cells). Where the vocabulary splits into many unrelated groups, the remaining pairs
  need a full similarity test, and the gain is small (1.3× on 400 separate vocabularies).
- **Relations, rule mining and inference** cost the same. After the fix, inference was the largest stage in the
  company world (46-48% of CPU), and categories still were in the gates world (67%).
- **Inference:** on data whose rules chain widely (the dpkg package graph in `studies/stress`), `INFER ALL` takes
  almost all the time and memory (59 s and 3.1 GB for 14,296 facts), and no category setting changes that.

**Checking it on your data.** The answers are the same either way; if you want to see that for yourself, compare
once:

```python
import egm
def answers(**s):
    with egm.open("facts.txt", settings={"MAXWORDS": 40000, **s}) as e:
        return {(f.fact, f.tier) for f in e.infer_all()}, sorted(r.text for r in e.rules())
assert answers() == answers(CLUSTERSTREAM=0)
```
