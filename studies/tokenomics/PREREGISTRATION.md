# Tokenomics of programmatic distillation — pre-registration

Written before any agent run of this study.

## Question
As the knowledge base grows, does answering through EGM keep an LLM's token cost flat and its accuracy high? And does reading a facts file, or reading the code, become more expensive or less accurate?

## Fixed across conditions
**Questions.** The same 36 engineering questions about Requests 2.32.3: lookups, callers of a changing function, caller modules, exceptions in one hop, grandparents and imports. They are generated with seed 2026 from the parser facts (`hidden/key.json`). The Requests facts were checked to be identical in all three corpora, so every question has the same answer at every size.

**Corpora.** Facts are built by the static parser (`tools/facts_multi.py`) with package-qualified names:
| Corpus | Packages | Facts | Bytes |
|---|---|---|---|
| S | Requests | 584 | 36.8 KB |
| M | + urllib3, Click | 2,490 | 153 KB |
| L | + Jinja2, Flask, Werkzeug | 6,621 | 412 KB |

**Model.** Claude Haiku sub-agents. They may not write or run code, may use only their allowed resource, and answer in JSON.

## Conditions
| Condition | Who answers | What it may use | Run at |
|---|---|---|---|
| H+EGM(size) | Haiku | only the `egm_<size>` command (ASK queries, logged) | S, M, L |
| H+notes(size) | Haiku | only `corpus/<size>.txt` (Read) | S, M, L |
| H+code(L) | Haiku | only the six package source directories (Read, Grep) | L |
| EGM-script(size) | no LLM | fixed one- or two-step queries per question type | S, M, L |

## Metrics
- **Mean F1:** exact match for single answers, F1 for lists.
- **Tokens, tool calls and wall time:** as reported by the agent runtime.
- **EGM CPU time.**

## Hypotheses
- **T1 (flat cost).** H+EGM tokens at L ≤ 1.3× its tokens at S, while H+notes tokens at L ≥ 2× its tokens at S.
- **T2 (accuracy).**
  - H+EGM mean F1 ≥ 0.95 at every size.
  - At L, H+EGM F1 ≥ H+notes F1, and H+EGM F1 ≥ H+code F1.
- **T3 (cost at L).** H+EGM uses fewer tokens than both H+notes and H+code.
- **T4 (ceiling).** EGM-script F1 ≥ 0.95 at every size, with zero tokens.

## Economics, computed from the measurements
For each size, the break-even number of question sets against H+code and H+notes, under two extraction scenarios:
- **(a) parser extraction:** zero tokens;
- **(b) LLM extraction:** 36.4 tokens per line of code, as measured on Requests in the previous study.

Projections beyond one question set assume the same cost per set; they are labelled as such.

## Limits
- One run per condition.
- Agent token counts include each agent's fixed context.
- Rules are enforced by instruction only.
