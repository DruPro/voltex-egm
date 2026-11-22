# Inferred programs: results

Pre-registered: `PREREGISTRATION.md` (hashes in `prereg_hash.txt`). The architecture map is `MAPPING.md`. Numbers
come from `results/results.json` (`tools/run.py`); verdicts from `tools/verdicts.py`. The engine was not changed.

**Hypothesis:** Voltex can learn a program from examples, then execute it by repeatedly applying its learned rules
to changing state, without treating runtime state as new learning evidence.

**Answer: yes, within one inference pass, for every program shape tested.** Across passes it also holds today for
composition rules. For tree rules it doesn't yet: a gate in the refresh path (`REFRESH`) makes every state change
relearn. That gap is narrow and specific.

## Verdicts

| Prediction | Verdict |
|---|---|
| H1 one pass: correct, nothing derived is ever stated, one build, output rules unchanged by runtime state | **pass** |
| H2 across passes, composition program: correct; rules learned once, refreshed (not relearned) at each step | **pass** |
| H3 across passes, tree program: relearns at every state change even with `REFRESH`, and costs ≥ 3× | **pass** |
| H4 chunked unrolling: cost per step falls monotonically, and K = 256 is ≥ 10× cheaper than K = 1 | **fail** (×7.13; K = 256 is slower than K = 32) |
| H5 provenance: every proof reaches stated facts; every rule used traces to its examples, with the engine's count | **pass** |
| H6 failure: no wrong law-tier output; execution stops at the first undecidable step | **pass** |

## X1: learned programs executed in one inference pass

| Program | Right | Derived facts stated | Builds | Output rules, with vs without runtime state | Proofs reach stated facts | Rule support = engine's count |
|---|---|---|---|---|---|---|
| P1 state machine (unrolled) | 1,280 / 1,280 | 0 | 1 (+0 later) | identical (6) | 40/40 | 6/6 |
| P3 recursion | 858 / 858 | 0 | 1 (+0 later) | identical (7) | 40/40 | 4/4 |
| P4 8-bit adders | 90 / 90 | 0 | 1 (+0 later) | identical (9) | 40/40 | 9/9 |
| P5 Rule 110 | 480 / 480 | 0 | 1 (+0 later) | identical (6) | 40/40 | 3/3 |

- **The programs:** a state machine (64 steps per run), recursion (ancestry along 12-long chains), circuits (8-bit
  adders) and an automaton (Rule 110). Each ran as learned rules applied round after round to derived state, inside
  one inference pass.
- **Runtime state was never learning evidence.** No derived value was stated. The rules that compute the program's
  outputs were the same whether the runtime part was in the knowledge base or not.

## X4: a trace back to the original examples

Every checked answer has a proof that reaches stated facts. Every rule it used was traced, outside the engine, to
the taught examples that support it, and the recovered counts equal the engine's `k` in all
22 rules. So a complete trace exists:

```
answer  <-  derivation (engine proof: rule + premises, recursively)  <-  inputs given at run time
rule    <-  its supporting examples (matched against the taught facts; count = engine's k)
```

One rule of the state machine, with three of its supporting examples:

```
TREE [? is output of ?](a,g) & [? has first input ?](g,y1) & [? has value ?](y1,s0) & [? has second input ?](g,y2) & [? has value ?](y2,b1) => [? has value ?](a,s1)
  n = 64 matches, k = 64 with the conclusion stated (engine: 64); e.g. p260 has value s1, p264 has value s1, p268 has value s1
```

## X2 and X3: execution across passes (the state changes between passes)

| Program | `REFRESH` | Right | Full relearns | Refresh builds (rules kept) | ms per step |
|---|---|---|---|---|---|
| P2 pointer walk | 0.05 | 200/200 | 0 | 199 | 0.9 |
| P2 pointer walk | 0 | 200/200 | 199 | 0 | 2.26 |
| P1 state machine (loop) | 0.05 | 64/64 | 63 | 0 | 19.09 |
| P1 state machine (loop) | 0 | 64/64 | 63 | 0 | 19.18 |

| Steps per pass (K) | Passes | Right | ms per step |
|---|---|---|---|
| 1 | 256 | 256/256 | 33.93 |
| 8 | 32 | 256/256 | 6.89 |
| 32 | 8 | 256/256 | 4.1 |
| 256 | 1 | 256/256 | 4.76 |

- **Composition programs need no relearning today.** With `REFRESH`, the walk learned its rule once, then ran 200
  steps on refresh builds: 0.9 ms per step against 2.3 ms with relearning. The harness replaces the state with
  `RETRACT` and `INGEST`, reusing existing names.
- **Tree programs relearn at every state change.** The state machine relearned 63 times in 64 steps, with or
  without `REFRESH`, at about 19 ms per step. The reason is in the engine: `remapRules` re-attaches only the three
  relation slots of a two-premise rule. Tree, path and condition rules carry more relation references (branches,
  path steps, the condition relation), so `ensureModel` switches the refresh path off for them.
- **Chunking is an external mitigation.** Laying out K steps per pass cut the cost 8× (K = 32), but not past the cost
  of one large pass. It also needs the next K steps' structure in advance. That's fine for a state machine over a
  known input, but not for computation whose next step depends on its result, unless it is recast as a local rule
  over a laid-out grid.

## X5: when no rule applies, rules conflict, or the state is unknown

| Case | Wrong law-tier answers | First step without a law answer | Law answers after it |
|---|---|---|---|
| a: a symbol never taught (b2 at step 12) | 0 | 12 | 0 |
| b: one transition taught with mixed outputs (first needed at step 1) | 0 | 1 | 0 |
| c: a start state never taught (s3) | 0 | 0 | 0 |

Execution stops exactly at the first step no law-tier rule decides, and nothing after it is computed.

## The questions, answered

- **Can the existing inference machinery execute an inferred program?** Yes. Inference applies a fixed rule list
  round after round over stated and derived facts, which is execution. Learning (rule mining) reads stated facts
  only.
- **Can successive rounds run over changing state without rebuilding the statistical and induction layers?**
  - Within a pass: yes, always.
  - Across passes: yes for composition rules (the refresh path); not yet for tree, path or condition rules.
- **What is the minimum external machinery?** A loop that holds the current state, replaces it between passes
  (`RETRACT`, `INGEST`) using existing names, and stops on halt or unknown. Or, when the steps' structure is known
  in advance, none: unroll and run one pass.
- **Can derived results feed later inference without becoming stated evidence?** Within a pass, yes, by design. To
  cross a pass the harness has to restate the new state. With the refresh path it is then re-projected but not
  learned from; otherwise it is learned from.
- **How are given inputs, derived state and learned rules told apart?** Answers are labelled stated or inferred
  (with tier and proof), and rules are separate objects. Missing: runtime inputs and taught examples are both
  "stated", and only the refresh path keeps runtime inputs out of learning.
- **Can a trace reach the original examples?** Yes, completely: the engine's proof to the given inputs, plus each
  rule's supporting examples, recovered externally. The counts were exact.
- **No rule, conflicting rules, unknown state?** Execution stops at the first undecidable step, with no wrong
  law-tier answer.
- **Recursion, state machines, circuits, more general structures?** All four ran as learned programs in one pass.
  Unbounded computation needs the loop, because inference can't create entities or overwrite values within a pass.

## Is an engine change justified? (the pre-registered decision rule)

1. **H3 confirmed:** tree programs relearn on every state change.
2. **The external alternatives don't match the refresh path:**
   - one-pass unrolling needs the whole space-time structure in advance;
   - chunking reached 4.1 ms per step at best, against 0.9 ms for a composition program on the refresh path, and
     can't follow computation whose next step depends on its result.
3. **The candidate is narrow and general:** let `remapRules` re-attach every relation a rule references (tree
   branches, path steps, condition relation), then lift the gate for those rule kinds. It is domain-free. It would
   be opt-in through `REFRESH` (off by default) and byte-identical when off.

So the rule says a change is justified to **propose**. It has not been made. It would go through `docs/EVALUATION.md`
§7: pre-registration, gate and stress bench byte-identical with it off, and this study's programs (with Mimic) as
the confirmation, with the same answers as a full relearn.

## What this does not show

- Five programs and one machine; the cost scale is small knowledge bases (2,000-20,000 taught facts).
- `REFRESH` also requires that no new words appear, so a harness must reuse names. Programs that need fresh entities
  each step (an unbounded tape) still need a full build, unless their cells are recycled.
- The exceptions problem (`studies/strengths`) and the snapshot loss (`lang/mimic/repro_observe_loss.py`) are
  separate and unchanged.
