# Architecture comparison: pre-registration

Status: pre-registered before any architecture code or run. Hash in `prereg_hash.txt`. Design and alternatives:
`DESIGN.md`. Method: `docs/EVALUATION.md`. The engine is not changed.

## Workloads (four, with different shapes; two aren't Mimic)

| | Workload | Shape | Truth |
|---|---|---|---|
| W1 | Mimic busy beaver, and increment on 32 ones | **sequential**: each step depends on the last | Mimic's reference interpreter |
| W2a | Mimic `add8`: 32 evaluations with random inputs | **independent** problems, deep circuits | reference interpreter |
| W2b | "What if" questions on a knowledge base (`tests/worlds.staff`): 40 new people, each put on a team, and the question "where are they based?" | **independent** problems, a knowledge workload | the generator: a team's city |
| W3 | Three domains (`company`, `gates`, `lineage` from `studies/noise`), in one engine or in three | **isolation** | generator truth |
| W4 | Two domains that a question has to compose: people → city (staff), and city → country (a geography world that teaches "based in C, C in K ⇒ from K") | **composition** across domains | generator truth |

W1 and W2a use one knowledge base holding the taught sets of all 8 Mimic programs ("one engine for everything"),
unless an architecture says otherwise.

## Architectures (`DESIGN.md` §4)

- **A, single engine.** Runtime facts are ingested and kept.
- **B, single engine with external working memory.** Runtime facts are ingested for the question and retracted
  after it. Independent problems are batched into one change: W2 with batch sizes 1, 8 and 32.
- **C, isolated engines.** One engine per program or domain, holding only its own taught set, with working memory
  as in B. W2 also splits batches across 1, 2, 4 and 8 parallel engines.
- **D, hybrid.**
  - **Static engine:** a knowledge engine holding everything taught, which never receives runtime facts.
  - **Temporary engines:** one per problem batch, built from the relevant taught subset plus the batch, then
    discarded.
  - **Mixed questions:** W2b asks the static engine 20 direct knowledge questions between batches.
- **E, external executor.** Applies the law-tier tree rules exported from an engine (`rules()`) to runtime facts
  outside the engine, without asking it. W1 and W2a only, since they're tree rules.

## Metrics

- **Correctness:** right, wrong or unknown against truth.
- **Proof preservation:** share of answers with a proof whose leaves are stated facts. Across engines, the
  orchestrator stitches the proofs.
- **Cost:**
  - median latency per answer;
  - throughput (answers per second) by number of parallel engines;
  - number of relearns, and relearn time;
  - peak resident memory summed over concurrent engines (`VmHWM` of each engine process).
- **Stability:** the knowledge engine's rule set before and after the workload.
- **Isolation (W3):** rules spanning relations of two domains; derived answers, one engine against three.
- **Complexity:** orchestrator lines of code per architecture; engines started.
- **Generality:** the architecture layer contains no workload-specific code. Workloads plug in through one adapter
  interface; checked by reading.

## How differences are judged

- **Repeats:** each cost cell runs 3 times.
- **Differences:** a cost difference counts only if it exceeds both 10% and 3× the cell's run-to-run spread. The
  bench validation measured 0.98-1.06 timing noise.
- **Disqualification:** any wrong answer, or a lost proof, disqualifies that architecture on that workload,
  whatever its speed.
- **No overall winner:** the comparison is reported per workload shape (sequential, independent, isolation,
  composition).

## Predictions

- **Q1.** A, B, C and D give the reference answer on every W1, W2a and W2b problem.
- **Q2.** W1 (sequential): C's time per step is lower than A's and B's. B is not faster than A.
- **Q3.** W2 (independent): B with batch 32 has at least 4× lower time per answer than B with batch 1.
- **Q4.** W2: C's throughput with 8 parallel engines is at least 3× its throughput with 1.
- **Q5.** W3: the three-engine answers equal the one-engine answers on every domain. The one-engine run accepts no
  rule joining relations of two domains.
- **Q6.** W4: composition across two engines gives the one-engine answers, each with a stitched proof reaching
  stated facts in both engines.
- **Q7.** E: on W1 and W2a it gives exactly the engine's answers, and is at least 10× faster per answer than A.
- **Q8.** The knowledge engine's rule set is unchanged after the workload in B and D; in A it changes at least once
  across W1 and W2.
