# Voltex v2.2 (EGM) validation and LLM vs EGM — pre-registration

Written after v2.2 was built and gate 1 passed (no envelopes ⇒ byte-identical to v2.1, 22/22), and before any other v2.2 run, any LLM run, or any look at seeds 31–35, 41 or 42.

## What v2.2 changes, and only that
v2.2 is the source-aware design (D) from the previous study plus four roadmap items. The reasoning substrate (word classes, relation formation, rule mining, inference) is v2.1's, unchanged.

| Item | Switch (default) | What it does |
|---|---|---|
| R1 compact log | always | The observation log stores record ids, not fact text. |
| R3 change signal | `CHGREMOVALS 1` | Only records that lost or replaced a fact feed v2.1's change signal (`touched`). |
| R5 same-value fix | `SAMEFIX 1` | In explained staleness (`DX 1`), a stale candidate that the linking rule still derives from current facts is confirmed, not marked "unknown". Inert when `DX 0`. |
| R6 refresh | `REFRESH 0` (off) | While changes since the last full build are ≤ the given share of records and add no new word, keep the learned word classes and rules; rebuild only relations and inference. |

## Part 1: v2.2 validation
Seeds 31–35, using the previous study's scenario suite unchanged (`evolve/exp_evo.py`, three worlds, 23 scenarios, one scenario per session, true late arrival for out-of-order).

Conditions:
- **D:** the previous study's binary;
- **V22:** v2.2 defaults;
- **V22off:** `CHGREMOVALS 0`, `SAMEFIX 0`;
- **V22x:** v2.2 defaults with `DX 1`;
- **B:** AMEND, unchanged.

Hypotheses:
- **V1 (equivalence):** V22off and D give identical answers on 100% of probes.
- **V2 (change signal):** V22's "two homes at once" set probe is right ≥ D's. No scenario's right rate drops by more than 1 point against D.
- **V3 (storage):** V22's people-world saved state is ≤ 1.5× v2.1's (D was 4.4×).
- **V4 (same-value fix):**
  - V22x's same-region-move probe: false "unknown" ≤ 5%.
  - V22x's stale-field probe: ≥ 10 points above V22.
  - If both hold, explained staleness is recommended on (`DX 1`), and the EGM configuration in Part 2 uses it. Otherwise Part 2 uses v2.2 defaults.
- **V5 (refresh):**
  - **Timing:** people world, scale 4, 50 updates, a query after each. With `REFRESH 0.02`, total time is ≤ 0.5× the full-rebuild time.
  - **Answers:** across the suite's people-world sessions replayed with a query after every observation, ≥ 99% of the queried answers are identical to full rebuild.
- **V6 (no regression):** on the base knowledge base of every world-seed, v2.2's accepted rule set is identical to v2.1's.

## Part 2: LLM vs EGM — does enriching the evidence fix reasoning failures for any reasoner?
**Design: 2 representations × 3 reasoners.**
- **Plain:** every fact, one per line, in arrival order; base first, then updates. This is the same information condition C received.
- **Enriched:** the same facts grouped in their observation envelopes: `[source=… record=… time=… revision=… snapshot|partial] fact; fact; …`.
- **Reasoners:**
  - EGM (v2.2, configuration chosen by V4): plain ⇒ INGEST, enriched ⇒ OBSERVE;
  - Claude Sonnet and Claude Haiku, run as sub-agents.

**Data.** Seeds 41 and 42, all three worlds, 5 instances per scenario (to keep two-value subjects well under 10%), one combined evidence file per world-seed. Out-of-order cases use true late arrival.

**Questions.** About 300 per seed, the same for every reasoner, in natural language with fixed answer formats:
- one value, or UNKNOWN / CONFLICT;
- a set, or UNKNOWN / CONFLICT;
- YES / NO / UNKNOWN;
- CURRENT / PAST / NEVER / UNKNOWN;
- conflict YES / NO.

**Rules for the LLMs.** They read only their evidence file and the question file, must not write or run code, and answer in JSON. Rules are enforced by instruction only. The answer key is held outside the files they are told to read.

**Scoring.** The same grades as the evolve study (right / wrong / ambiguous / abstain), against the hidden truth.

Probe classes:
- **change-sensitive:** change, stale, correction, out-of-order, removals, history and conflict probes;
- **change-insensitive:** compatible facts, partial omission, kept dependency, two values in a new relation, new relationship.

Hypotheses:
- **L1 (EGM):** enriched beats plain by ≥ 30 points (right rate) on change-sensitive probes, with no loss > 2 points on change-insensitive probes.
- **L2 (LLMs):** enriched beats plain by ≥ 10 points on change-sensitive probes, for each model.
- **L3 (enriched):**
  - EGM's pooled wrong rate is ≤ each LLM's;
  - EGM's right rate on history probes is ≥ each LLM's.
  - Where an LLM beats EGM, it is reported.
- **L4 (cost):** wall time and, for LLMs, the tokens reported by the agent runtime.

No tuning on these seeds. Exploratory analyses are labelled.
