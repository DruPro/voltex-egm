# Real-data replication sets (Round 1 confirmation)

Built by `realdata.py build` on the machine that runs the confirmation; `realdata/manifest.json` records the Python
version, the Unicode database version, the sha256 of `/var/lib/dpkg/status`, and per split the counts and a hash of
the stated facts. The split files themselves (134 MB) are not committed: they are regenerated deterministically from
the same sources and seeds.

## The sets

| Set | Source on this machine | Facts (split 1000) | Truth | Hidden per split |
|---|---|---|---|---|
| `py_stdlib` | CPython 3.13 standard library, `/usr/lib/python3.13` (tests excluded) | 66,105 stated | complete: every base and target fact, from Python's own `ast` (`studies/strengths/tools/extract.py`, round 2 fact design) | 30% of target facts (subclass, package, binding), by subject |
| `py_dist` | installed third-party packages, `/usr/lib/python3/dist-packages` | 77,329 stated | as above | as above |
| `unicode` | Unicode 15.1 characters U+0020-U+2FFF (`studies/stress/layers/world.py`) | 30,074 stated | the same relations computed from Python's `unicodedata` for every named character, so a true fact about a character outside the extracted range is scored true | 20% of facts |
| `dpkg` | installed Debian packages, `/var/lib/dpkg/status` | 7,081 stated | the database's own direct facts (depends on, recommends, provides, section, priority, architecture, source) | 20% of facts |

Five splits per set, seeds 1000-1004 (hiding seed; the extractor's fixed seed 11 replaced by the split seed).
Recall is measured on each split's hidden facts; precision against the complete truth.

**dpkg truth, stated before the run:** "A depends on B" means a direct dependency, as the database records it. A
derived transitive dependency is therefore not a true fact under this definition and counts as wrong. The stress study
showed that this choice matters a lot (precision 0.080 against direct facts, 0.876 against the transitive closure),
so the report also gives, as a secondary view that counts for no criterion, how many derived `depends on` facts lie in
the transitive Depends closure.

## Independence from Round 1's development

- None of these sets was used during Round 1's development (G4): iterations 1-4 used only the synthetic capability
  catalogue (`studies/capability`). No built-in policy value or acceptance threshold was set on them.
- The sources are not new to the project: earlier studies (`studies/strengths`, `studies/stress`) used the same kinds
  of data with earlier engine versions, on another machine. The dpkg case from the stress study (a law-tier rule at
  0.15 agreement) motivated iteration 1's agreement floor; that floor was replaced in iteration 4 for reasons found on
  the synthetic worlds, and the dpkg data were not run.
- Seen before the confirmation run: one `policy-tendency` run per set on split 1000, for timing (DEVIATIONS.md D1).
  Nothing was changed afterwards.
- `MAXWORDS` = distinct words + 1,000 for every profile, the documented capacity step (docs/CHOOSING_SETTINGS.md),
  fixed before the run.
