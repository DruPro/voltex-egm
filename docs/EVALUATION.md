# Evaluating Voltex: is the engine getting better?

This is the repository's standard for judging an engine change. Every claim that Voltex improved has to answer to
it. It asks whether a general capability measurably improved without degrading what already worked, not whether a
feature was added or a benchmark went up.

- **Baseline numbers:** `studies/eval/BASELINE.md`, generated from `studies/eval/baseline/`.
- **Study template:** `studies/PROTOCOL_TEMPLATE.md`.
- **Validation of the framework's own measurements:** section 9.

## 1. Principles

1. **Measure mechanisms, not applications.** A capability is tested on controlled synthetic worlds whose truth is
   known completely, and is replicated on independent data. Real applications, such as code or package databases,
   check usefulness. They don't set the architecture.
2. **Every rate comes with its counts.** "Precision 1.00" with zero new facts is not a result. A rate with nothing
   to divide by is reported as undefined.
3. **Variance before thresholds.** Acceptance criteria are tied to the baseline's spread across seeds, and are fixed
   before the confirmation runs.
4. **Opt-in and equivalence.** A new behaviour is off by default, and output with it off is byte-identical to
   before, on every gate and bench cell.
5. **Development and confirmation are separate.** What was tuned on is never the evidence for the tuning.
6. **Parameter recovery is not optimality.** A setting found on one dataset is evidence about that dataset.
   Replication on independent data strengthens it; it doesn't make it a default.
7. **No guessing.** The engine and its tools must say when something is unknown, uncertain or only weighted.
   Evaluation checks this directly (calibration, controls, empty answers).
8. **Passing tests is necessary, not sufficient.** Tests pin behaviour. They are not evidence of generality.

## 2. The capabilities and how each is measured

Each capability is owned by one layer of the architecture (`docs/THEORY.md`, section 3): storage, statistics,
induction, inference, evidence view, presentation.

### 2.1 Representation (storage, statistics)

What can be stated and become a relation. Facts are word sequences. A relation is a template with two open slots,
found when at least 3 records share it, and there are at most `MAXRELATIONS` (40) of them. Slots hold single tokens;
categories cover the `MAXWORDS` most frequent words.
- **Measured by:** whether the stated facts are recovered as relations (`RELATIONS`); `[LIMIT]` lines; the stress
  bench's shape datasets (multi-word values, many relations, messy text).
- **Metrics:**
  - relations found against relations generated;
  - share of the vocabulary inside categories;
  - facts that fall outside any relation.

### 2.2 Induction (induction)

Discovering rules from observations.
- **Measured by:** worlds with known rules, varied one knob at a time:
  - sample size: `company` scale;
  - sparsity: `hidden` coverage;
  - noise: `company` and `hidden` noise;
  - redundancy: reports;
  - no rule at all: a control world.
- **Metrics:**
  - accepted rules that are true or false (against the generator's rules where known);
  - precision and recall of the facts they produce;
  - false discoveries on controls;
  - rule errors per 1,000 facts as data grows (`studies/noise`).

### 2.3 Expressiveness (induction)

Which rule structures can be learned and applied:
- **inverse and symmetric:** default;
- **two-step composition and transitivity:** default;
- **paths of 3 to 8 premises:** `CHAIN`;
- **group conditions:** `CONDITIONS`;
- **trees, where several branches meet at one entity:** `TREES`;
- **higher-arity relations:** only through reification, such as a gate entity with input, kind and output relations.

- **Measured by:** one world per structure, with a setting off (expected: nothing) and on:
  - lineage (paths);
  - harvest (conditions);
  - gates and adders (trees, layered computation).
- **Metrics:**
  - recall and precision with the structure on;
  - output with it off (should be nothing);
  - cost.

### 2.4 Inference (inference)

Deriving new facts, and how depth, branching and conflicting evidence affect them.
- **Measured by:** `DEPTH` sweeps on long chains (remainders, adders); conflict-bearing worlds (`hidden` with
  contradictions); proof structure (`CHAINS`: round and tendency steps per fact).
- **Metrics:**
  - precision and recall by depth;
  - growth of the derived set per round (flood detection);
  - share of answers resting on tendency steps.

### 2.5 Evidence and reliability (inference, evidence view, presentation)

Telling stated, inferred, law, tendency, conflicting, stale and unknown apart.
- **Measured by:** tier calibration (scorecard); conflict flags against injected corruptions (`lib.score`:
  `flagged`, `flag_hits`); empty-answer notes and `[LIMIT]` reporting (tests).
- **Metrics:**
  - **calibration:** precision of law-tier and of tendency-tier new facts, separately. The engine's claim is that
    law means estimated reliability of at least `LAW` (0.95);
  - **flag precision and recall** against known corruptions;
  - **invented facts** about names never seen.

### 2.6 Evolution (evidence view)

Change, correction, staleness, and conflict with newer evidence.
- **Measured by:** SDK tests (snapshot to history, sources disagree, stale and current); the stress bench's update
  script (cost); `studies/scaling` (incremental cost). The quantitative evolution studies (`evolve`, `egm22`,
  `declarative`) are archived and need path changes to rerun.
- **Metrics:**
  - answers that match a full recompute after each change (equivalence);
  - stale facts flagged out of those invalidated;
  - update cost as a share of a cold build.

### 2.7 Efficiency and scalability (all layers)

- **Measured by:** the stress bench (time and peak RSS per cell, under a memory cap); `studies/scaling` (stage
  timings, complexity fits); `egm bench` (query latency).
- **Metrics:**
  - ingest time;
  - learning time (rules, on the first question);
  - inference time;
  - query latency (p50 and max);
  - peak memory;
  - scaling exponent with facts and vocabulary.

  Report these phases separately; "time" alone is ambiguous.

## 3. Capability matrix

| Capability | Layer | Current support | Known boundaries (evidence) | Measured by | Missing measurements |
|---|---|---|---|---|---|
| Representation | storage, statistics | two-slot templates, 2-8 open words, ≥ 3 records, ≤ 40 relations, single-token slots | multi-word values give no relation (stress `phrases`); names seen once can't fill a slot (THEORY §7.4); rarer words beyond `MAXWORDS` are in no relation (`studies/tendency` T5) | stress shape datasets; `[LIMIT]`; kit cold-start test | relations found vs generated, as a standing metric; polysemy (one token, two meanings) and synonymy (two tokens, one meaning) |
| Induction | induction | counting with base-rate lift and known-answer agreement; coverage correction | coincidence errors recede with data (`noise` H1a); sparse or skewed data admits rules on thin evidence (stress dpkg: law tier at 0.15 agreement) | scorecard sample-size and sparsity cells; `studies/noise` grids; stress bench | rule-level truth (accepted rules vs generator rules); false discovery rate on controls across sizes |
| Expressiveness: paths | induction | `CHAIN` 2-8 | lineage solved at `CHAIN 3`; coincidence-rich data loses precision (hidden world −0.024 at 3, `multipremise` H2) | scorecard lineage; `studies/multipremise` | path length vs sample size needed |
| Expressiveness: conditions | induction | `CONDITIONS` on accepted rules, evaluated by the shared evidence vector, validation and policy admission (`studies/shared_conditions`) | spurious conditions from 9 cases (`multipremise` R2); a proxy condition in 1 of 5 seeds of `hidden` at 70% (`shared_conditions`); proposal is in-sample | scorecard harvest; `shared_conditions` (independent held-out worlds: 5/5); Round 2 confirmation: `conditional_rare` (8% qualify) precision and recall 1.0 in 5/5 seeds, no harm on any other world, recommended as default (`studies/round2/CONFIRMATION.md`) | conditions on more than one attribute; conditions resting on few subjects (`CONDHOLDOUT` drops them; in development that cost 3 true conditions in 10 seeds) |
| Expressiveness: trees | induction | `TREES` joining branches at one entity; targets must be one-value relations with at most 8 distinct values (`mineTrees`; `studies/harness` deviation 1) | needs an anchor entity one step from the fact's subject (`strengths` deviation 1); costly on large data (stress company ×8: 2 → 35 s) | scorecard gates; `studies/trees` (adders); `studies/compute` (NAND-only adders, 3-input Rule 110, 16 × 16 automaton) | branch count vs data needed; noise robustness at scale; a base-rate shortcut ("an AND gate outputs zero") competing with exact rules; examples needed grow when the predicted value is the majority value (`studies/harness` H2: 64 per transition) |
| Expressiveness: same-direction copy | induction | not a shape | `r(a,b) ⇒ s(a,b)` is unlearnable; state the inverse (`strengths` deviation 1) | `studies/strengths` round 1 | none: a known boundary |
| Higher arity | storage, induction | through reification only | no direct n-ary facts | gates, adders (reified) | a direct n-ary benchmark (for example, 3-place events) |
| Inference as program execution | inference | learned rules applied round after round over derived state, without learning from it: a state machine, recursion, circuits and an automaton run in one pass, with output rules unchanged by runtime state and proofs traceable to the supporting examples (`studies/inferred_program`) | across passes, rules are kept with `REFRESH` for composition and tree rules (`studies/refresh_trees`); path (`CHAIN 3+`) and condition rules still relearn; each step still re-projects relations and reruns full inference (2.5-2.7× cheaper than relearning, not more); a change that only removes facts always relearns (unsigned change counter) | `studies/inferred_program`, `studies/refresh_trees` | the gap's cost at larger knowledge bases; programs needing fresh entities per step |
| Inference: depth | inference | `DEPTH` rounds or fixpoint; bounded computation (circuits, unrolled automata; `studies/compute`) | wide graphs flood (dpkg ×4 per round); `DEPTH 0` ran out of memory on dpkg | scorecard remainders; `studies/depth`; stress dpkg | flood detection as a standing metric (growth per round) |
| Inference: conflicts | inference | one-value voting, two distinct rules to contradict | general rules outvote exact specific ones (`strengths`, both codebases) | `lib.score` flags; `studies/noise` | specificity vs vote on a controlled world |
| Reliability: tiers | inference, presentation | law (≥ `LAW`) or tendency, per rule and per fact | law can be wrong when the extractor omits values (`strengths` replication); law at 0.15 agreement on dpkg | scorecard calibration; `strengths` tier counts | why tendency-tier precision falls as coverage rises (`hidden`: 0.94 → 0.55); calibration on real data as a standing metric |
| Reliability: policies (voltex3, experimental) | inference, presentation | configurable, versioned policies (`docs/POLICIES.md`); built-ins legacy (default), strict, tendency; stratified inference, closed and nested answers, faithful proofs | confirmed: nesting, no invention, proof validity and faithfulness, legacy byte-identical. Not confirmed: strict precision ≥ 0.95 (fails on conditional structure, 0.047, and dpkg, 0.006, as `TENDENCYSTEPS 0` does); a better risk-coverage ranking (`studies/evidence_policy/CONFIRMATION.md`) | `studies/capability` suite; `studies/evidence_policy/confirm`; `studies/round2` | Round 2: `COVSOURCE` removes the dpkg-like flood (400,000 → 1,308 new facts, all hidden facts kept) but stays opt-in (H1 failed: strict lost that world's recall); strict still not precise because an inverse rule can be its own coverage source; `minStability` did not raise precision on confirmation |
| Reliability: unknown | presentation | empty = "unknown, not false", names `[LIMIT]` caps (MCP, SDK) | gaps can be filled at law tier from population majority (`strengths`) | `tests/test_mcp.py`, `test_sdk.py` | how often inferred values fill gaps the facts never constrained |
| Learned-operation programs (Mimic) | outside the engine | `lang/mimic`: functions, machines, circuits and automata taught by example; 14/14 definitions learned, 0 wrong results in 3 execution modes (`lang/mimic/bench`) | relation phrases differing in one word with a shared tail confuse slot choice; constant outputs can't be learned; recursive top-down questions match `DEPTH 0` at 13× the questions | `lang/mimic/bench`, `tests/test_mimic.py` | selective (demand-driven) evaluation on flooding data |
| Computation with a harness | outside the engine | the engine learns a step function; a harness supplies memory and iteration (`studies/harness`: a busy beaver and binary increment from a learned transition table) | about 85 ms per step, because each step rebuilds; the engine alone stays bounded | `studies/harness` | longer programs; incremental inference for per-step cost |
| Evolution | evidence view | OBSERVE envelopes: snapshot, partial, history, sources disagree, uncertain, stale, re-derivation; a record's current snapshot is lost after 13-26 restatements when plain facts also name its entity (`lang/mimic/repro_observe_loss.py`) | an update with a new name costs a full rebuild; `REFRESH` 23-36% (`scaling` I1, I2) | SDK tests; stress update cells; `studies/scaling` | a runnable correction/staleness benchmark (archived studies need paths) |
| Efficiency | all | `CLUSTERSTREAM` categories; 244,444 facts in 256 MB | rule mining with `TREES` dominates large runs; inference memory unbounded with `DEPTH 0` | stress bench; `studies/scaling`; `egm bench` | complexity fits for rule mining and inference, not only categories |

## 4. The protocol for an engine change

Every step maps to a file the repository already uses (`studies/PROTOCOL_TEMPLATE.md`).

| Step | What | Where it lives |
|---|---|---|
| 1 | State the capability or limitation | `PREREGISTRATION.md` §1, citing a matrix row |
| 2 | Identify the owning layer | §2 |
| 3 | Falsifiable hypothesis | §3 |
| 4 | Baseline before any change, with seed variance | §4; `studies/eval/tools/scorecard.py` |
| 5 | Worlds, controls, metrics, expected failure modes | §5 |
| 6 | Development vs held-out confirmation | §5; development results labelled exploratory |
| 7 | Accuracy, coverage, false discoveries, calibration, cost, provenance | §5; section 5 below |
| 8 | Replicate on independent environments | §8 |
| 9 | Document trade-offs and new limitations | `RESULTS.md`; `DEVIATIONS.md` for any change of plan |
| 10 | Decide | §10: adopt as experimental or stable, keep as an option, or reject |

`prereg_hash.txt` records the sha256 and UTC time of each pre-registration before its first run.

## 5. Metrics

| Metric | Definition | Tool |
|---|---|---|
| Precision (with count) | new facts true ÷ new facts; undefined when there are no new facts | `lib.score`, scorecard |
| Recall (with count) | hidden or missing true facts recovered ÷ missing; undefined when nothing is missing | same |
| False discoveries on controls | new facts on a world with no structure, or about a decoy | scorecard `random_links`; `studies/trees` T2 |
| Invented facts | new facts naming an entity never observed | `lib.score` `invented_unseen` |
| Calibration | precision of law-tier and tendency-tier facts, separately, against `LAW` | scorecard |
| Flag precision and recall | conflicts raised on injected corruptions ÷ conflicts raised; ÷ corruptions | `lib.score` |
| Coverage | share of vocabulary in categories; questions answerable vs asked | `[LIMIT]`; `egm.bench` |
| Flood | new facts per inference round | `CHAINS` |
| Cost | ingest, learning, inference, query p50 and max, peak RSS | stress bench, `egm bench`, `studies/strengths/tools/query_time.py` |
| Provenance | every derived fact has a proof whose leaves are stated facts | `ask` `because`; `explore.py proof()` |
| Equivalence | byte-identical output per cell with a change off | `gate.py`, `bench.py compare` |

## 6. Improvement, regression, general and dataset-specific

- **Improvement.** A capability metric moves beyond the baseline's seed range on the target worlds; it replicates
  on an independent environment; and no regression appears anywhere.
- **Regression.** Any of these, on any registered world or bench cell:
  - a metric falls below the baseline's range;
  - a control gains false discoveries;
  - calibration worsens (law-tier precision falls);
  - an equivalence cell differs with the change off;
  - an existing test fails or is weakened;
  - cost rises beyond what was declared.
- **General improvement.** It holds on at least two independent generators or environments, at several sizes, with
  the same settings, and with no tuning on the confirmation data.
- **Dataset-specific result.** It holds on one dataset, or only after tuning on it. Report it as that. It can
  justify an opt-in setting, never a default.
- **Neutral.** Within the baseline range everywhere. A neutral change with extra cost is a regression in efficiency.

## 7. Adding a capability without compromising the rest

1. Add it behind a setting, off by default (the `CONFIG` registry marks it experimental).
2. Run the gate (221 cells) and the stress bench (294 cells) with it off. Both must be byte-identical to the
   baseline, under the same tool version.
3. Run the scorecard with it off (identical) and on (measured).
4. Run `make test`, `make repro` and `make sanitize`. Never remove or weaken a test; add tests for the new
   behaviour.
5. Run on independent data. Report cost and new limitations.

## 8. Reporting limitations honestly

- **Failures next to wins,** in the same table.
- **Counts with every rate.** Undefined rates stay undefined.
- **What the result does not show,** stated explicitly: one dataset, one seed, one tuning.
- **Separate what the engine decided from what the extractor made true.** Check whether a learned rule is true by
  construction of the extraction.
- **Law tier is "reliable given what was observed"**, not truth about the system.
- **Exploratory is labelled exploratory.** Numbers are recomputed from results files by a script, never retyped.

## 9. Validation of these measurements (run on this repository)

Each tool the framework relies on was re-run on the current `main` to check that its measurements reproduce. The
results are in `studies/eval/validation/`, and the numbers in `studies/eval/BASELINE.md`, generated by
`studies/eval/tools/report.py`.

| Check | Result |
|---|---|
| `make test`, `make repro` | 30/30 kit checks and all unit tests; 7/7 published results |
| Gate: current build vs itself | 221/221 identical |
| Gate sensitivity: one side with `RATE 0.3` | 47 of 221 cells differ, so the gate detects a behaviour change |
| Gate: current build vs a rebuild of `ac54dd9`, from before `CLUSTERSTREAM` and C1 | 221/221 identical |
| Stress bench vs its recorded C1 run | 294 of 295 identical; 1 not comparable (memory cap on both) |
| Timing noise, same engine, unshared machine | 0.98-1.06 × the recorded time (15 cells ≥ 1 s) |
| Scorecard, run twice | identical per-seed results in 17 of 17 cells |

What the first baseline shows (`studies/eval/BASELINE.md`, 5 seeds per cell):
- **Law-tier calibration held everywhere.** Law-tier precision was at least 0.988 in every cell and seed,
  above the engine's claimed 0.95.
- **Tendency-tier precision is not calibrated.** It ranges from 0.03 (harvest, without `CONDITIONS`) to 1.00, and
  varies by seed. In the `hidden` world it has sd up to 0.24, and it falls as coverage rises:
  0.94 at 30%, 0.55 at 70%. The number of tendency-tier facts stays about the same (300-340), while law-tier facts
  fall with less missing, so tendencies become a larger share. Overall precision falls with coverage too (0.987 →
  0.915). Why tendency precision falls is not established; it is an open measurement (matrix, "Reliability: tiers").
  Tendency is a weighted guess, as labelled, and its precision has to be measured per dataset.
- **Each structure is off without its setting and on with it.** Gates 0 → 0.786 recall (`TREES`); lineage 0 →
  1.000 (`CHAIN 3`); harvest precision 0.029 → 1.000 (`CONDITIONS`); remainders 0.853 → 0.924 (`DEPTH 0`). The
  no-structure control derives nothing.
- **The seed spread sets the bar for "beyond the baseline".** For example, company with 15% noise has recall
  0.782 ± 0.121, so a change has to beat that spread, not one run.

## 10. Audit: what exists, and what this framework adds

The existing infrastructure, which the framework uses rather than replaces:

| Tool | Measures | Run |
|---|---|---|
| `make test` | 30 kit checks (engine determinism, SAVE/LOAD identity, CLI) and the SDK and MCP unit tests | `make test` |
| `make repro` | the 7 published results (Requests, tokenomics S/M/L) | `make repro` |
| `make sanitize` | address and undefined-behaviour sanitizer build | `make sanitize` |
| `studies/scaling/tools/gate.py` | byte-identical equivalence, 17 datasets × 13 settings | `python3 gate.py A B` |
| `studies/stress/tools/bench.py` | 31 datasets × settings × scripts: output hash, time, peak RSS, precision and recall against held-out keys | `bench.py run BIN OUT`, `bench.py compare` |
| `studies/noise/tools/lib.py` and `hidden/gen.py` | controlled worlds with knobs (scale, coverage, noise, reports, contradictions) and complete-truth scoring | used by the gate and the scorecard |
| `tests/worlds.py` | small deterministic worlds per structure (lineage, gates, remainders, harvest, staff) | used by the tests and the scorecard |
| `egm.tune` | settings per dataset, by holdout | `egm tune` |
| `egm bench` | ingest and query timing | `egm bench facts.txt` |
| `studies/stress/tools/explore.py`, `verify.py` | learned rules, proofs, full-truth checks on real data | per study |
| `studies/strengths/tools/` | exact-truth scoring on real code, with tiers and per-phase timing | per study |

Findings of the audit:
- **Calibration and seed variance were not standing measurements.** They are now in the scorecard
  (`studies/eval/tools/scorecard.py`).
- **No control world was run routinely.** The scorecard includes one.
- **`lib.score` reports 1.0 for undefined rates.** For example, precision with no new facts. The scorecard reports
  them as undefined; `lib.py` is unchanged, because other studies' results depend on it.
- **Stored cell hashes depend on the tool version.** The gate's normalisation changed (`bcb6b42`) after
  `studies/scaling` recorded its hashes. So equivalence is proven by re-running both binaries under one tool
  version, and results files should record the tool commit (the scorecard does).
- **Benchmarks that share the machine distort timing.** The stress study's two hash reruns ran side by side and
  were about 1.45× slower. Its timing verdicts used the sequential timed runs, so no claim is affected. Rule: time
  only on an unshared machine, and record whether a run was alone.
- **Tendency-tier precision varies across seeds and coverage.** sd up to 0.24 in the `hidden` world. A single run
  can't support a claim about it.
- **Evolution has no runnable quantitative benchmark.** The archived studies name `/home/claude/...` paths.
- **`docs/THEORY.md` §7.6 lists the rule shapes as of v2.2.** It predates `CHAIN`, `CONDITIONS` and `TREES`; the
  matrix above is current.
- **The study index (`studies/README.md`) didn't list `stress`, `strengths` or `eval`.** Added.
