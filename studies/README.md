# Studies

Every experiment behind the papers and the engine's settings, in the order they were run. Each
folder holds what the study used and produced: pre-registration (where there was one), world
generators, hidden answer keys, the inputs the engine and any LLM subjects saw, harnesses and
scorers, raw answers, agent audit logs, and the results files the write-ups cite.

| Study | What it tested | Write-up |
|---|---|---|
| [`v1_audit/`](v1_audit/) | Audit of Voltex v1: what the code actually computes | `docs/papers/Voltex Research & Architectural Assessment.pdf` |
| [`v21_baseline/`](v21_baseline/) | Frozen Voltex v2.1 baseline and its gates | `docs/papers/Voltex Research & Architectural Assessment.pdf` |
| [`v2_containment/`](v2_containment/) | Voltex v2: rule discovery, PCA agreement, benchmarks | `docs/papers/Evidential Grammar Memory A Rule-Discovering, Self-Correcting Memory Tool for La.pdf` |
| [`improve/`](improve/) | Improvement experiments: tiers, retraction, refresh, scoring | `docs/papers/Voltex Improvement Experiments Findings and Decisions.pdf` |
| [`blind_world/`](blind_world/) | Blind world discovery | `docs/papers/Voltex Blind World Discovery Results.pdf` |
| [`amend/`](amend/) | AMEND: amendments as operations | `docs/papers/Amendments in Voltex an experiment.pdf` |
| [`declarative/`](declarative/) | Declarative amendments through evidence ingestion | `docs/papers/Declarative amendments in Voltex can a change be knowledge instead of an operati.pdf` |
| [`evolve/`](evolve/) | Dynamic relational evolution: where should change live | `docs/papers/Dynamic relational evolution in Voltex where should change live.pdf` |
| [`egm22/`](egm22/) | Voltex v2.2 (EGM) validation, and LLM vs EGM | `docs/papers/Evidence Before Inference Source-Aware Observation Enrichment for Evolving Knowl.pdf` |
| [`realcode/`](realcode/) | Real codebase: LLM-extracted facts plus EGM retrieval | `docs/papers/Extract Once, Query Forever LLM-Extracted Codebase Facts in Evidential Grammar M.pdf` |
| [`tokenomics/`](tokenomics/) | Tokenomics of programmatic distillation | `docs/papers/Tokenomics of Programmatic Distillation EGM Keeps an LLM's Query Cost Flat as Kn.pdf` |
| [`code_facts/`](code_facts/) | Standard-library code facts graded by an AST parser | `docs/papers/Extract Once, Query Forever LLM-Extracted Codebase Facts in Evidential Grammar M.pdf` |
| [`company/`](company/) | Company world: clean and noisy (15%, 30%) data | `docs/papers/Evidential Grammar Memory A Rule-Discovering, Self-Correcting Memory Tool for La.pdf` |
| [`agentlab/`](agentlab/) | Agent lab: Haiku and Sonnet with search vs with Voltex | `docs/papers/Tokenomics of Programmatic Distillation EGM Keeps an LLM's Query Cost Flat as Kn.pdf` |
| [`explain_apples/`](explain_apples/) | Explanations and the 'are apples blue?' demonstration | `docs/THEORY.md` |
| [`math/`](math/) | Mathematics by example: divisibility and remainders | `docs/THEORY.md` |
| [`programming_by_example/`](programming_by_example/) | Programming inference by example | `docs/THEORY.md` |
| [`demo/`](demo/) | Demonstration session used in the posts | `media/` |
| [`config/`](config/) | Settings saved with the knowledge base (6/6 checks passed) | `studies/config/RESULTS.md` |
| [`depth/`](depth/) | Inference depth: `SET DEPTH 0` runs to a fixpoint | `studies/depth/RESULTS.md` |
| [`multipremise/`](multipremise/) | Rules with 3+ premises (`CHAIN`) and group conditions (`CONDITIONS`) | `studies/multipremise/RESULTS.md` |
| [`trees/`](trees/) | Tree-shaped rules (`TREES`): gates, 4-bit adders, hidden world | `studies/trees/RESULTS.md` |
| [`noise/`](noise/) | Noise: does it recede with data? `VOTE`, `QUARANTINE`, `REPLICATE`, and `egm tune` | `studies/noise/RESULTS.md` |
| [`tendency/`](tendency/) | A user control for answers resting on tendencies (`TENDENCYSTEPS`), `CHAINS`, capacity limits, rebuild time, redundancy in the pipeline | `studies/tendency/RESULTS.md` |
| [`shard/`](shard/) | Sharding as an external layer: a clean boundary, rule consensus, a central stage; identical answers to one engine up to 244,444 facts | `studies/shard/RESULTS.md` |

## How the earlier studies were archived

The first 18 folders were copied from the working area where they ran by
[`archive_studies.py`](archive_studies.py), unedited. Each has an `ARCHIVE.md` that lists:

- **Packed folders.** Log and data folders over 2 MB are stored as one `.tar.xz` each
  (`tar -xJf logs.tar.xz`). Together they unpack to about 800 MB.
- **Binaries left out.** Compiled engines, with the sha256 of each copy used. Every one was
  built from a `.cpp` in its folder or from `src/voltex2.cpp`.
- **Third-party material left out.** Downloaded packages (click, flask, jinja2, rich, urllib3,
  werkzeug, requests) and the typeshed stubs bundled with mypy, with their versions.
- **Absolute paths.** Scripts that name `/home/claude/...`, where the studies ran. Adjust those
  paths, or recreate that layout, to rerun.

The six later studies (`config`, `depth`, `multipremise`, `trees`, `noise`, `tendency`) were written in place and run
against this repository's engine; their tools take the engine path from the `VOLTEX` variable.

## Ground rules all studies followed

Pre-registration before the first real run (hash and timestamp in `prereg_hash.txt` or
`prereg_time.txt`), deviations logged, hidden answer keys never shown to the engine or to LLM
subjects, controls that must produce nothing, several seeds, and failures reported next to the
wins. A study's own `RESULTS.md` or paper is the authority for its numbers.
