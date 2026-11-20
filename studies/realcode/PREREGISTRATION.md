# Real-codebase use case: LLM-extracted facts + EGM retrieval — pre-registration

Written after the ground truth and questions were generated, and before any agent run.

**Codebase:** Requests 2.32.3 (PyPI source, `src/requests`, 18 modules, 5,642 lines). It was only parsed, never executed.

**Ground truth:** `tools/truth.py` statically parses the code into five relations (274 definitions, 165 resolved calls, 45 raises, 47 inheritance links, 55 imports). Calls count only where they resolve statically to a package function or method (`self.m` through the class hierarchy, module-level functions, imported package functions). It is an approximation of runtime behaviour, used the same way for every condition.

**Questions:** 36, from `tools/make_questions.py` (seed 2026):
- 8 lookups;
- 8 callers of a function whose signature is changing (impact analysis);
- 4 caller modules (a two-step join);
- 6 exceptions raised directly or through a direct callee (two steps);
- 5 grandparent classes (two steps);
- 5 module imports.

Each agent receives only the question text and answer format. The answer key is in `hidden/`.

## Pipeline
1. **Extraction (once).** A Claude Haiku sub-agent reads only `src/requests/*.py` and writes facts in five fixed sentence templates to `public/facts.txt`. It may not write or run code. Extraction quality is scored against the truth (precision and recall per relation).
2. **EGM.** Voltex v2.2 ingests `facts.txt` with plain INGEST (a single snapshot, so no envelopes are needed). Relations and rules are learned from those facts alone.

## Conditions (all answer the same 36 questions)
| | Who answers | What it may use |
|---|---|---|
| **H+EGM** | Haiku sub-agent | only the `egm` command (EGM queries over the extracted facts); no code, no facts file |
| **H+notes** | Haiku sub-agent | only `facts.txt` (the same extracted knowledge, without EGM) |
| **H+code** | Haiku sub-agent | only the source directory (Read and Grep) |
| **EGM-script** | no LLM | a fixed mapping from each question type to EGM queries (one or two ASK steps) |

**Metrics:**
- **Answer quality:** exact match for single answers, and F1 for list answers (exact match is reported too).
- **Cost:** tokens and time per agent, as reported by the runtime.

**Amortisation:** we report the number of questions after which extraction plus EGM queries cost fewer tokens than reading the code (H+code tokens per question vs extraction tokens).

## Hypotheses
- **R1:** H+EGM mean F1 ≥ H+code mean F1 − 0.05, with fewer solver tokens than H+code.
- **R2:** H+EGM ≥ H+notes on the two-step questions (caller modules, raises in one hop, grandparents).
- **R3:** EGM-script's F1 is within 0.05 of H+EGM, which would mean EGM retrieval, not the LLM, carries the answers.
- **R4:** extraction recall by relation is reported. Errors are expected to propagate into every condition that uses `facts.txt`.

**Limits stated in advance:**
- one codebase, one run per condition;
- the static truth approximates runtime behaviour;
- agent rules are enforced by instruction only.
