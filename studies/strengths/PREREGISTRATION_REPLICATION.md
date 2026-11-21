# Strengths study: replication on an independent codebase

Status: pre-registered before any engine run on this data. Hash in `prereg_hash.txt`.

## Why

Rounds 1-3 used one codebase, the CPython standard library. A good result there could be a property of that one code
base. `docs/CHOOSING_SETTINGS.md` already recommends round 3's settings for exact parser output, so the
recommendation has to hold on code written by other people.

## Data (fixed)

- **Codebase:** `/usr/lib/python3/dist-packages` on this machine: Debian's Python packages, tests excluded. This is
  third-party code (pip, apt, PIL, yaml, attrs, cloud-init and others), not the standard library.
- **Size:** 2,918 files and 1,027,745 lines, giving 171,223 facts and 71,529 words. Ancestry chains run up to 13
  ancestors.
- **Extraction:** `tools/extract.py --r2` with `OBS_DIR=obs_dist`, unchanged except for two fixes made before this
  file:
  - path filters now apply to the path relative to the root;
  - a function whose token equals a module's token gets a `__fn` suffix (1 case, `pip._internal.main`).

  The stdlib output is byte-identical after both fixes (sha256 checked).
- **Hidden facts:** by subject, seed 11, 17,635 facts:
  - `is bound to`: 9,260;
  - `belongs to package`: 6,819;
  - `is a subclass of`: 1,556.

## Runs (fixed; no tuning on this data)

- **Settings:** round 3's `TENDENCYSTEPS 0`, plus `MAXWORDS 72600` (the vocabulary plus about 1,000, the same
  rule as before).
- **Runs:** `default`, `depth1`, `chain3`, `trees`, and `full` (`TREES 1`, `CHAIN 3`, `DEPTH 0`).

## Predictions

- **X1:** in `full`, precision is at least 0.99 on each target relation, and nothing is derived in a non-target
  relation.
- **X2:** in `full`, recall is at least 0.95 on each target relation.
- **X3:** in `full`, at least 99.9% of law-tier new facts are true.
- **X4:** package recall is below 0.10 in `default` and at least 0.90 in `chain3`. Binding recall is below 0.10 in
  `default` and at least 0.90 in `trees`.
- **X5:** every run finishes in under 15 minutes and 4 GB.
