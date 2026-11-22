# Where should runtime state live? Architectural alternatives for computing with Voltex

**Status (2026-11-22): paused, not run.** The owner refocused the work on whether learned rules can themselves be
executed as programs (`studies/inferred_program`); the architecture question is secondary to that. This design and
its pre-registration stand as written (hashes in `prereg_hash.txt`) and can be run later.

Original status: research and design, written before any architecture code. The experiments are pre-registered in
`PREREGISTRATION.md`; results will be in `RESULTS.md`. The engine is not changed.

## 1. The question

Mimic (`lang/mimic`) and the harness study (`studies/harness`) both feed runtime state into the engine that holds
the learned knowledge: a machine's current state, or a circuit's inputs. Every such fact triggers relearning. The
question is not "how do we make the engine cheaper", but **which component should own each responsibility**:
- evidence and learning;
- inference and proofs;
- mutable state;
- iteration;
- routing.

An engine change is justified only for what no external design can do.

## 2. What the existing system provides (researched, with measurements)

| Capability | Today | Evidence |
|---|---|---|
| Learned model persistence | **None.** `SAVE` stores the evidence (facts, observation log, settings); the model is rebuilt on the first question after `LOAD` | `studies/scaling` I3: reopening costs 102-109% of a cold build |
| Rule import or export | **None.** There is no command to give an engine rules; rules exist only as what an engine learned from its own facts. `rules()` reads them as text | `HELP`; `egm/engine.py` |
| A question on an unchanged knowledge base | **Cheap:** 0.01-0.12 ms (3k-49k taught facts) | measured below |
| A question after any change | **A full relearn** (categories, relations, rules) plus inference: 37 ms at 3k taught facts, 208 ms at 12k, 1.7 s at 49k | measured below; `studies/scaling` I1 |
| Partial rebuild (`REFRESH`) | Reuses categories and rules only for small changes with no new words, and **never** with `TREES`, `CHAIN 3+`, `CONDITIONS`, `REPLICATE` or `QUARANTINE` on | `src/voltex2.cpp`, `F_REFRESH` condition |
| Removing a fact | `RETRACT` removes it exactly, and the next question relearns | `HELP` |
| Several engines | `egm.shard`: one engine per independent source, run in parallel, with optional consensus. Exact on a clean boundary; splitting one fact set is not general (2 of 6 world shapes) | `studies/shard`, `studies/shard_general` |
| Engine processes | One OS process per engine; starts in about 3 ms; this machine has 8 cores and 23 GB | measured |
| Change as evidence | `OBSERVE` snapshots and history. The current snapshot is lost after 13-26 restatements in some conditions | `lang/mimic/repro_observe_loss.py` |

Measured on the busy-beaver program's taught examples (one change = ingest one step and ask; exploratory, before
this design; `tools/primitives.py` re-measures them, with `MAXWORDS` sized, as part of the experiments):

| Taught facts | Learn | Question, nothing changed | One change, then question |
|---|---|---|---|
| 3,072 | 40 ms | 0.01 ms | 37 ms |
| 12,288 | 230 ms | 0.12 ms | 208 ms |
| 49,152 | 2,400 ms | 0.07 ms | 1,729 ms |

**Consequence.** For any architecture, cost ≈ (number of changes made to an engine) × (relearn time of that engine's
taught set). Relearning grows faster than linearly with the taught set. Questions without changes are almost free.
So an architecture can win only by:
- making fewer changes per answer (batching);
- making each changed engine smaller (isolation);
- running engines in parallel (8 cores here);
- not asking the engine at all (executing exported rules elsewhere).

## 3. What can be done externally, and what can't

- **Externally:**
  - mutable state, iteration, scheduling and termination (the harness already does this);
  - routing questions to engines;
  - batching independent problems into one change;
  - removing working facts after use (`RETRACT`), so the knowledge engine returns to its taught state;
  - creating and discarding temporary engines;
  - composing results across engines by stating one engine's answer as another's input, with the proof stitched
    by the orchestrator.
- **Only with a new engine capability:**
  - answering about new facts **without relearning**. That needs either facts that are not evidence (working
    memory) or a persisted learned model that a new engine can load instead of relearning;
  - importing rules into an engine.

  Without these, any engine that answers a question about a new state must relearn its taught set.

## 4. The alternatives

| | Architecture | Knowledge | Runtime state | Engines |
|---|---|---|---|---|
| A | Single engine (Mimic `fresh` today) | one engine | ingested into it and kept | 1 |
| B | Single engine + external working memory | one engine, back to its taught state after each problem | held outside; ingested only for the question, then retracted; independent problems batched | 1 |
| C | Several isolated engines | one engine per domain or program, with only its own taught set | per engine, as in B | one per domain, in parallel |
| D | Hybrid | a static knowledge engine that never sees runtime state | temporary engines, each built from the relevant taught subset plus one problem's state, then discarded | 1 static + temporary, in parallel |
| E | External executor (for comparison) | engines learn rules; an external executor applies the exported rule text to runtime state | outside | 1 + executor |

E is included because "don't ask the engine at all" is the cheapest possible execution. It moves inference
semantics (voting, tiers, conflicts) out of the engine, which risks diverging from it and duplicating it. It must
be measured against the engine's own answers, and is judged on that risk, not only on speed.

## 5. Expected trade-offs (hypotheses, not results)

- **A:** simplest. Rules drift as runtime state accumulates (`studies/harness` H1b), and each change relearns
  everything taught to it.
- **B:** keeps the knowledge clean and rules stable. A change still relearns everything. Batching helps only when
  problems are independent; a machine's steps are sequential, so they can't be batched.
- **C:** a smaller taught set per engine means cheaper relearning, and engines run in parallel. Cross-domain
  questions need orchestrated composition, and the proofs then span engines. Isolation also removes rules that would
  otherwise be learned across domains: good when those rules are coincidences, bad when they are real. Known from
  `studies/shard`: exact when the boundary keeps each fact's evidence together.
- **D:** like C, plus a stable knowledge engine for direct knowledge questions. Each temporary engine pays a full
  learn, so it pays off only when one engine serves many changes or problems run in parallel.
- **E:** fast. Its correctness and proof fidelity relative to the engine are the open question. It adds a second
  inference implementation to maintain.

## 6. What would justify an engine change

An engine capability (working memory, or model persistence) is justified only if the best external architecture
leaves a cost or correctness gap that matters for a real workload, and the capability closes it while staying
general: domain-free, opt-in, and byte-identical when off. The experiments measure that gap.
