# Strengths study: results

The data is the CPython 3.13.7 standard library: 273,430 lines in 534 files, extracted with `ast`. Round 2 has
65,679 facts and 27,398 words. The 5,901 hidden facts are scored against the complete truth.
Every number here is recomputed by `tools/report.py` from `results*/`. Design: `PREREGISTRATION.md` and rounds 2-3;
why the rounds exist: `DEVIATIONS.md`. The charts and proof trees are in `report/index.html`.

## Verdicts

| Prediction | Round 1 | Round 2 | Round 3 |
|---|---|---|---|
| P1 | pass | fail | pass |
| P2 | pass | pass | pass |
| P3 | fail | pass | pass |
| P4 | fail | fail | pass |
| P5 | pass | pass | pass |
| P6 | - | fail | fail |
| P7 | - | - | pass |
| P8 | - | - | pass |

- **Round 1** stated the facts naively.
  - **Targets the rules can't express:** two of the three. There is no same-direction copy shape, so a hidden class
    never got its direct parent, and nothing was learned for `binds`.
  - **What it got right:** zero wrong facts in every run, and `CHAIN 3` recovered all 1,414 package facts.
- **Round 2** stated the same ast facts in the engine's language.
  - **Recall:** 0.988 with all settings on.
  - **Precision:** 0.043 overall. Tendency-tier rules flooded `is a subclass of` and the base relations, giving 129,672 wrong facts.
- **Round 3** added `TENDENCYSTEPS 0`, the guide's setting for answers you act on.
  - **`full`:** 5,829 of 5,901 hidden facts recovered, with
    21 wrong facts out of 5,850.
  - **Tiers:** every law-tier answer is correct (5,829 of 5,829). All
    21 wrong answers are labelled tendency, so `ask(..., strict=True)` returns none of them.
  - **P6 fails.** With a parent's ancestry stated, the transitive rules span many generations in one round, so
    `DEPTH` changed only 8 facts.

## All runs

| Round | Run | New facts | Wrong | Precision | Recall | Subclass R | Package R | Binding R | s | MB |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `default` | 213 | 0 | 1.000 | 0.036 | 0.304 | 0.000 | 0.000 | 0.6 | 48 |
| 1 | `depth1` | 205 | 0 | 1.000 | 0.035 | 0.292 | 0.000 | 0.000 | 0.6 | 48 |
| 1 | `depth2` | 213 | 0 | 1.000 | 0.036 | 0.304 | 0.000 | 0.000 | 0.6 | 48 |
| 1 | `depth0` | 213 | 0 | 1.000 | 0.036 | 0.304 | 0.000 | 0.000 | 0.5 | 48 |
| 1 | `chain3` | 1,627 | 0 | 1.000 | 0.276 | 0.304 | 1.000 | 0.000 | 0.7 | 55 |
| 1 | `trees` | 213 | 0 | 1.000 | 0.036 | 0.304 | 0.000 | 0.000 | 4.2 | 68 |
| 1 | `full` | 1,627 | 0 | 1.000 | 0.276 | 0.304 | 1.000 | 0.000 | 4.2 | 68 |
| 2 | `default` | 120,438 | 119,737 | 0.006 | 0.119 | 1.000 | 0.000 | 0.000 | 20.8 | 269 |
| 2 | `depth1` | 2,222 | 1,528 | 0.312 | 0.118 | 0.990 | 0.000 | 0.000 | 0.9 | 67 |
| 2 | `depth2` | 32,801 | 32,100 | 0.021 | 0.119 | 1.000 | 0.000 | 0.000 | 1.2 | 118 |
| 2 | `depth0` | 130,352 | 129,651 | 0.005 | 0.119 | 1.000 | 0.000 | 0.000 | 96.5 | 269 |
| 2 | `chain3` | 125,121 | 123,006 | 0.017 | 0.358 | 1.000 | 1.000 | 0.000 | 43.4 | 274 |
| 2 | `trees` | 124,166 | 119,751 | 0.036 | 0.748 | 1.000 | 0.000 | 0.981 | 32.9 | 295 |
| 2 | `full` | 135,501 | 129,672 | 0.043 | 0.988 | 1.000 | 1.000 | 0.981 | 148.7 | 300 |
| 3 | `default` | 701 | 0 | 1.000 | 0.119 | 1.000 | 0.000 | 0.000 | 0.9 | 66 |
| 3 | `depth1` | 693 | 0 | 1.000 | 0.117 | 0.989 | 0.000 | 0.000 | 0.9 | 66 |
| 3 | `depth2` | 701 | 0 | 1.000 | 0.119 | 1.000 | 0.000 | 0.000 | 0.9 | 66 |
| 3 | `depth0` | 701 | 0 | 1.000 | 0.119 | 1.000 | 0.000 | 0.000 | 0.9 | 66 |
| 3 | `chain3` | 2,115 | 0 | 1.000 | 0.358 | 1.000 | 1.000 | 0.000 | 1.2 | 75 |
| 3 | `trees` | 4,429 | 14 | 0.997 | 0.748 | 1.000 | 0.000 | 0.981 | 10.2 | 210 |
| 3 | `full` | 5,850 | 21 | 0.996 | 0.988 | 1.000 | 1.000 | 0.981 | 10.5 | 210 |

## Exploratory: depth stress

The ancestry of 70% of classes is hidden (`extract.py --r2 --hide-sub 0.7`, 1,689 facts), with round 3 settings.

| Run | Subclass recall | Wrong | Facts by round |
|---|---|---|---|
| d1 | 0.9651 | 0 | {'1': 1630} |
| d2 | 0.9988 | 0 | {'1': 1630, '2': 57} |
| d3 | 1.0000 | 0 | {'1': 1630, '2': 57, '3': 2} |
| d4 | 1.0000 | 0 | {'1': 1630, '2': 57, '3': 2} |
| d0 | 1.0000 | 0 | {'1': 1630, '2': 57, '3': 2} |

The deepest answer is 5 generations long and is built in 3 rounds. `RotatingFileHandler` → `BaseRotatingHandler` →
`FileHandler` → `StreamHandler` → `Handler` → `Filterer`; every leaf of its proof is a stated `inherits from` fact.

## What it does not do (for the owner; decision stack, not changed)

**Exceptions to a general rule lose the vote.** The 72 hidden facts about `classmethod` and `staticmethod`
methods got no correct answer, though the exact rules were learned:
- the rules: `has decorator classmethod ⇒ binds cls` (1.00 on 116 known) and `staticmethod ⇒ nothing` (1.00 on 55);
- what happened: on the single-valued relation, the more general rules all vote `self`. These are "methods bind
  self" (0.97) and package- and class-specific variants of it;
- the result: 21 wrong answers, all labelled tendency, and 51 left unanswered.

Preferring the more specific rule, the one with fewer exceptions, would fix this, but that is a change to what the
engine decides.

## Replication on an independent codebase (`PREREGISTRATION_REPLICATION.md`)

- **Codebase:** Debian's Python packages (`/usr/lib/python3/dist-packages`): 2,918 files and
  1,027,745 lines. This is third-party code, with ancestry up to 13 ancestors.
- **Size:** 171,223 facts, with 17,635 hidden.
- **Settings:** round 3's, with no tuning on this data.

| Run | New facts | Wrong | Precision | Recall | Subclass R | Package R | Binding R | s | MB |
|---|---|---|---|---|---|---|---|---|---|
| `default` | 1,556 | 0 | 1.000 | 0.088 | 1.000 | 0.000 | 0.000 | 3.2 | 171 |
| `depth1` | 1,546 | 0 | 1.000 | 0.088 | 0.994 | 0.000 | 0.000 | 3.2 | 171 |
| `chain3` | 8,375 | 0 | 1.000 | 0.475 | 1.000 | 1.000 | 0.000 | 4.9 | 200 |
| `trees` | 10,511 | 59 | 0.994 | 0.593 | 1.000 | 0.000 | 0.961 | 36.9 | 536 |
| `full` | 17,359 | 88 | 0.995 | 0.979 | 1.000 | 1.000 | 0.961 | 39.5 | 536 |

Verdicts: X1 fail, X2 pass, X3 pass, X4 pass, X5 pass.

- **Generality:** the result holds. In `full`, 17,271 of 17,635 hidden facts were
  recovered (recall 0.979). 17,265 of 17,269
  law-tier answers are true. `CHAIN 3` and `TREES 1` are again the only route to the package and binding facts.
- **X1 fails, on 4 law-tier facts in a non-target relation** (`has decorator none`). The cause is the extractor. It
  writes no `has decorator` fact for functions whose decorators it doesn't handle (`@lru_cache` and the like), and
  the engine filled those gaps with the package's majority value. **Lesson:** if an extractor leaves out a class of
  values, the engine will predict the majority value for those entities, so state "other" explicitly.
- **The exception problem replicates.** Of the 370 hidden `classmethod` and `staticmethod` facts, 6 are right, 84
  wrong (all labelled tendency) and 280 unanswered. All 8,890 other hidden binding facts are right. So general rules
  outvoting exact specific ones is not specific to the standard library.

## Exploratory: can `egm.tune` find these settings? (`tools/tune_check.py`, `tune/`)

The holdout tuning ran on the stdlib facts (`obs_r2`): 3 folds × 15%, scored by F0.5.

| Search | Adopted | F0.5 | Evaluations | s |
|---|---|---|---|---|
| default space | `RATE 0.5` | 0.034 → 0.276 | 54 | 177.2 |
| expanded, hand-built (MAXWORDS 28500) | `TENDENCYSTEPS 0`, `CHAIN 3`, `MAXWORDS 28500`, `TREES 1` | 0.034 → 0.733 | 129 | 457.7 |
| `egm.tune(..., expanded=True)` | `TENDENCYSTEPS 0`, `CHAIN 3`, `MAXWORDS 28398`, `TREES 1` | 0.034 → 0.733 | 129 | 467.9 |

- **What it shows:** the expanded search found the hand-chosen configuration from the data alone. That shows the
  search can recover the right parameters on this dataset. It doesn't show that the configuration is best
  everywhere. On the tokenomics S set, the same search started from `TENDENCYSTEPS 0` reverted it to -1.
- **Defaults unchanged:** `expanded` is opt-in, and the default search is unchanged. After the change, default
  `tune()` gives the identical history on this data (`api_default.json`) and on tokenomics S, M and L.
