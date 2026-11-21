# Tendency study: results

Pre-registered 2026-11-20T21:15:25Z (`PREREGISTRATION.md`, sha256 bef20ba3…). No deviations. Two follow-ups, X1
and X2, were designed after seeing T1 and T7 and are labelled **exploratory**. Engine: one binary throughout
(sha256 a8bdd065…), the build of this commit.

The design rule this study follows: the engine stays general about which associations and relations it can
represent. How precise to be, which inferences to trust, and how the data is designed are the user's choices.
The engine exposes evidence, tiers, proofs and limits, and offers opt-in controls with measured trade-offs. **No
default changed.**

## Verdicts

| Hypothesis | Verdict | In one line |
|---|---|---|
| T1 `TENDENCYSTEPS 1` fixes the cascade (+0.30 precision) | **fail** | 0.023 to 0.023. `TENDENCYSTEPS 0` does fix it: 0.975. |
| T2 no correct answers lost on law-tier worlds | **pass at 1, fail at 0** | At 0, lineage loses 360 of 360 and harvest 54 of 54. |
| T3 trade-off table | descriptive | Below. |
| T4 defaults unchanged | **pass** | Gate 22/22 identical. |
| T5 capacity: limit reported; raising it recovers >= 95% | **pass** | `[LIMIT]` printed in 3 of 3 seeds; with `MAXWORDS 30000`, 3,198 of 3,198 outputs, 0 wrong. |
| T6 restoring a backup takes <= 3 s | **pass** | `LOAD` plus a first query: at most 1.39 s (19,062 facts). Full rebuild: at most 0.97 s. |
| T7 a pipeline majority filter matches VOTE | **fail** | 2 of 8 cells. Keeping tied values breaks it; X2 (drop ties) does better (below). |

## T1: what the cascade actually is (found with `CHAINS`)

`CHAINS` counts derived facts by inference round and by tendency steps in their proof. In a cascade cell (hidden,
coverage 0.9, seed 0, no noise), default settings gave:

| Round | 0 tendency steps | 1 | 2 | 3 |
|---|---|---|---|---|
| 1 | 885 | 1,159 | | |
| 2 | 113 | 2,378 | 129 | |
| 3 | 2 | 6,823 | 303 | 12 |
| 4 | | 29,265 | 609 | 16 |

The cascade is **not** tendencies built on tendencies. It is *one* tendency step, amplified by law-tier rules round
after round: inverse, symmetric and transitive family rules applied to wrong "parent" facts. So a limit of 1 leaves
it untouched (45,060 facts, precision 0.023). Only 0, no tendency step at all, stops it (962 facts, precision
0.975). My prediction modelled the wrong mechanism. The visibility tool is what showed the real one.

## T2/T3: the trade-off, by world

`TENDENCYSTEPS` | -1 (default) | 1 | 0

| World | Precision | Recall | Correct answers |
|---|---|---|---|
| company, clean | 1.000 / 1.000 / 1.000 | 0.963 / 0.840 / 0.499 | 1,118 / 976 / 580 |
| company, 15% noise | 0.990 / 0.987 / 1.000 | 0.803 / 0.682 / 0.219 | 1,003 / 851 / 274 |
| hidden, coverage 0.5, clean | 0.949 / 0.961 / 0.998 | 0.517 / 0.514 / 0.482 | 2,514 / 2,496 / 2,343 |
| hidden, coverage 0.9, clean | 0.261 / 0.264 / 0.981 | 0.630 / 0.628 / 0.594 | 1,045 / 1,040 / 984 |
| tree gates (5 seeds) | 1,319 / 1,319 / 1,332 correct, 0 wrong at each | | |
| adders, lineage, remainders, harvest | unchanged at 1 | | at 0: lineage 360 to 0, harvest 54 to 0 |

Means over seeds 0-2. Full table: `results_t1_t3.json`, `results_t2.json`.

- **`TENDENCYSTEPS 0`** gives answers that follow from law-tier rules only: precision 0.97-1.00 everywhere. The
  cost depends on how complete the data is.
  - A true rule whose conclusion is stated for only part of the data looks like a tendency (lineage: great-grandparent
    stated for 25 of 40 families; harvest: 90% of harvests stated), so it is switched off with the noise. That is
    "missing is not false" again.
  - In company it cut recall from 0.96 to 0.50, because the person-to-city rule is a tendency when only 30% of
    people's cities are stated.
- **`TENDENCYSTEPS 1`** costs little where tendencies don't chain (hidden at coverage 0.5: -18 correct, +0.012
  precision) and up to 15% of correct answers in company, where chained tendencies were right.
- Tree rules on gates gained 13 correct outputs at 0, because a competing tendency path was blocked.
- **Which setting is right depends on the data and the use, so it is the user's choice.** For a database export
  where every rule should hold: 0. For exploration: the default, read through the `law`/`tendency` labels.

**Exploratory X1** (`results_x1.json`): the existing `DEPTH` setting is a weaker brake on the cascade. At coverage
0.9, `DEPTH 1` precision was 0.52 and `DEPTH 2` 0.39. Neither reaches the 0.98 of `TENDENCYSTEPS 0`. At coverage 0.5,
`DEPTH 1` costs recall (0.52 to 0.38).

## T5: the capacity limit found in the audit

Gates at 800 per kind (16,016 words): with the default `MAXWORDS 12000`, the engine now prints
`[LIMIT] categories cover the 12000 most frequent of 16016 words; facts naming rarer words are in no relation (SET MAXWORDS)`
and derives 0 outputs. With `MAXWORDS 30000`: 1,034 / 1,070 / 1,094 of the hidden non-random outputs in seeds 0-2,
all correct, in about 9 s instead of 5. `MAXRELATIONS` (default 40) reports the same way. No limit was hit on any of
the 22 gate datasets, so their output is unchanged.

## T6: restoring a backup is cheap

| Data | Facts | Full rebuild from facts | `LOAD` + first query | Saved size |
|---|---|---|---|---|
| company scale 1 / 2 / 4 | 3,815 / 7,589 / 15,363 | 0.07 / 0.18 / 0.37 s | 0.09 / 0.23 / 0.58 s | 30 / 59 / 120 KB |
| hidden scale 1 / 2 / 4 | 4,078 / 9,038 / 19,062 | 0.10 / 0.32 / 0.97 s | 0.17 / 0.48 / 1.39 s | 32 / 70 / 148 KB |

So the practical way to correct a mistake is to fix the facts upstream and rebuild, or restore the last good
knowledge base, not to patch the engine's state. Both take about a second at these sizes. Timings are from this
2-core machine, measured while another experiment was running.

## T7/X2: can redundancy live in the data pipeline?

- **T7 (registered): a majority filter that keeps every tied value is worse than VOTE** in 6 of 8 cells. A subject
  reported 1x/1x/1x keeps three values, and the relation stops looking one-value. Company at 30% noise, 3 reports:
  precision 0.34 vs VOTE's 1.00.
- **X2 (exploratory): the same filter, but on a tie keep nothing** (the data cannot decide, so the value is unknown):

| Cell (means over 5 seeds) | VOTE precision / recall | Pipeline, ties dropped |
|---|---|---|
| company 15%, 3 reports | 0.998 / 0.954 | 0.9995 / 0.957 |
| company 15%, 5 reports | 0.999 / 0.958 | 1.000 / 0.959 |
| company 30%, 3 reports | 1.000 / 0.702 | 0.995 / 0.948 |
| company 30%, 5 reports | 0.936 / 0.851 | 0.997 / 0.956 |
| hidden 15%, 3 / 5 reports | 0.974 / 0.504, 0.960 / 0.499 | 0.964 / 0.510, 0.965 / 0.512 |
| hidden 30%, 3 / 5 reports | 0.979 / 0.466, 0.980 / 0.468 | 0.951 / 0.501, 0.964 / 0.508 |

- In company the pipeline matched or beat VOTE everywhere. At 30% noise it had much higher recall, because it
  declares which relations are one-value instead of inferring that from noisy data.
- In the hidden world it trades 1-3 points of precision for 1-4 points of recall. The extra answers are mostly
  tendency-rule answers, the same effect VOTE showed in `studies/noise`.
- Under the registered criterion (recall within 0.01 in either direction) X2 passes only 2 of 8, because its recall
  is often *higher*.
- Conclusion: redundancy can be handled in the data pipeline, where the developer knows which relations are
  one-value, provided ties become "unknown" rather than "all of them". VOTE remains the in-engine option for when
  the pipeline cannot do it.

## Philosophy check

- **The added control is opt-in and neutral.** It removes answers the user asked to exclude, and never adds or
  changes one. `CHAINS` and `[LIMIT]` only add information.
- **Generality.** The audit found no domain vocabulary in the core: the only English words are the amendment words of
  an experimental, off-by-default study. It found two silent capacity caps, which are now settings and are reported.
- **Corrections go upstream.** Fix the facts and rebuild, or restore a backup; at these sizes either takes about a
  second.

## Reproduce

```
export VOLTEX=$PWD/build/voltex2
cd studies/tendency
python3 tools/run_all.py all
python3 tools/x1_depth_alternative.py; (cd tools && python3 x2_pipeline_ties.py)   # exploratory
```

Worlds come from `studies/noise/hidden/gen.py`. A `contradict` argument was added to `hidden()`; its default keeps
every noise-study world byte-identical (checked).
