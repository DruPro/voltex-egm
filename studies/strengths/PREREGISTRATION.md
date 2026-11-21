# Strengths study: exact facts from one large codebase, scored against complete truth

Status: pre-registered before any engine run on this data. Hash in `prereg_hash.txt`.

## Why

The stress study (`studies/stress`) asked where the engine fails, on noisy extractions scored against a partial key.
This study asks the opposite question: what the engine does when its input is what it is designed for. That means
facts that are exact, structured and complete, with rules that really hold, and scoring that can't call a true
answer wrong. It is meant to show the engine at its best on real code. It does not replace the failure reports.

## Data (fixed)

- **Codebase:** the CPython 3.13.7 standard library, tests excluded (`tools/extract.py`): 534 files, 273,430 lines.
- **Extraction:** Python's own `ast` only (definitions are read; no call or type guessing). 51,814 stated facts,
  15,173 distinct words; no token names two kinds of entity (checked).
- **Base facts, all stated:**
  - `inherits from` (1,643), resolved bases only;
  - `is a method of` (9,672);
  - `is defined in` (2,210);
  - `is part of` (349);
  - `has scope` and `has decorator` (12,222 each).
- **Targets, exact functions of the base facts**, truth computed in full in `obs/truth.json`:
  - `is a subclass of`: the transitive closure of `inherits from`, up to 7 ancestors. Tests depth.
  - `belongs to package`: method → class → module → package, 3 hops with no shortcut relation stated. Tests
    multi-premise rules.
  - `binds self|cls|nothing`: what Python passes as the first argument. Scope and decorator decide it together. Tests
    trees.
- **Hidden by subject, seed 11** (5,901 facts in `obs/key.txt`):
  - 701 `is a subclass of` facts (all such facts of 30% of classes);
  - 1,414 `belongs to package` facts;
  - 3,786 `binds` facts.

## Scoring

- **Precision** is computed against the complete truth: a new fact is wrong only if it is false about the code. New
  facts in non-target relations are wrong too, since those relations are complete.
- **Recall** is the share of hidden facts recovered, per relation.
- **Base settings for every run:** `MAXWORDS 16200`, step 1 of `docs/CHOOSING_SETTINGS.md`.

## Runs (fixed)

| Name | Settings added |
|---|---|
| `default` | none |
| `depth1`, `depth2`, `depth0` | `DEPTH` 1, 2, 0 |
| `chain3` | `CHAIN 3` |
| `trees` | `TREES 1` |
| `full` | `TREES 1`, `CHAIN 3`, `DEPTH 0` |

## Predictions (each passes or fails as written)

- **P1, depth.** Recall on hidden `is a subclass of` does not fall as `DEPTH` rises (1 ≤ 2 ≤ 4 ≤ 0). Precision on it
  is at least 0.95 at every depth.
- **P2, multi-premise.** `belongs to package` recall is below 0.10 in `default` and at least 0.90 in `chain3`, with
  precision at least 0.95 in `chain3`.
- **P3, trees.** In `trees`, `binds` recall is at least 0.95 with precision at least 0.99.
- **P4, combined.** `full` recovers at least 90% of all 5,901 hidden facts at overall precision at least 0.95.
- **P5, cost.** Every run finishes in under 15 minutes and 4 GB.

Everything beyond these is exploratory and labelled so.
