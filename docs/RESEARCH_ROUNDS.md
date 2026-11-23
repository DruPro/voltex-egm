# Running a research round: the tooling

`docs/EVALUATION.md` says how changes are judged. `docs/DEVELOPING.md` section 5 says what a round produces. This
guide covers the tools a round uses, in the order you use them. Round 2 (`studies/round2/`) is the worked example.

## 1. The capability suite (`studies/capability/`)

It measures what a relational inference engine should do (capabilities C1 to C13 in `studies/capability/README.md`),
against complete three-valued truth, through one fixed interface, so that any engine can be scored, not only EGM.

| Tool (`studies/capability/tools/`) | What it gives you |
|---|---|
| `interface.py` | `EGMAdapter(settings, policy=...)` runs EGM and returns a `Run` of `Answer`s (fact, status, confidence, proof, rule). `parse_fact`. Any engine with `run(lines, rels, probes)` can be scored. |
| `cworlds.py` | the development worlds (`CATALOGUE`: company, noisy, hidden at three coverages, gates, lineage, harvest, remainders, random_links). `load(name, seed)` returns a `World` with truth, recall truth, corruptions and undeterminable queries. |
| `metrics.py` | `measure(world, run)`: precision, recall, new, wrong, AURC (risk over the engine's own ranking), P@R50, invented unseen facts, abstention, retention, flag precision and recall, proof validity, cost. |
| `baselines.py` | B0 stated only, B1 majority value, B2 one-hop inverse, B3 AMIE-style rule mining. A change that doesn't beat these isn't progress. |
| `metamorphic.py` | C9 consistency: renaming, reordering and duplicating facts must not change the answers. |
| `counterfactual.py` | C10 faithfulness: remove a proof's premise and check that the answer goes away or another proof replaces it. |
| `profile.py` | every profile on every development world: `python3 profile.py --seeds 5 --md /tmp/dev.md --title "..."`. The G3 baseline is `BASELINE.md`; never overwrite it from a development run. |

A minimal development comparison:

```python
import sys; sys.path[:0] = ["studies/capability/tools"]
import cworlds, metrics
from interface import EGMAdapter
for seed in range(5):
    w = cworlds.load("hidden-cov70", seed)
    for name, eng in {"default": EGMAdapter({}), "covsource": EGMAdapter({"COVSOURCE": 1}, policy="tendency")}.items():
        m = metrics.measure(w, eng.run(w.lines, w.rels, []))
        print(seed, name, m["precision"], m["recall"], m["aurc"])
```

`studies/round2/dev/w1_compare.py` and `w3_compare.py` are fuller versions, with policies built in code
(`dataclasses.replace` on a built-in) and real-data splits.

## 2. Sealed generators (confirmation worlds)

Confirmation needs worlds the developer didn't design against. Each round's generator is written by a separate agent
from a structure spec and the output format, without reading the engine:

| Generator | Structures | Use |
|---|---|---|
| `studies/sealed/gen_sealed.py` | 14 (inverse, transitive, composition, path3, conditional and its decoy and control, branching, depth, noise, hub, ambiguous, …) | Round 1 confirmation; Round 2 development |
| `studies/sealed2/gen_sealed2.py` | 10 with rules of mixed, known quality in one world (reversed_weak, graded, skewed, multivalue, exceptions, competing, sparse, conditional_rare, chain_noise, control_degree) | Round 2 confirmation |

```
python3 studies/sealed2/gen_sealed2.py graded 7 /tmp/w      # facts.txt, key.json
python3 studies/sealed2/gen_sealed2.py --check              # the author's self-check
```

`key.json` holds complete truth, the hidden facts (recall truth), undeterminable queries (`[rel, subj]`, or
`[rel, subj, obj]` for many-valued relations), corruptions, the generating rules and, in Round 2, each rule's measured
precision (`rule_quality`). Once a generator's seeds have been used for a confirmation, they are development data for
the next round.

To commission the next generator: write `SPEC.md` (purpose, output contract, structures with defaults and what each
is meant to separate), then hand an agent only that file and the format section of the previous README, with an
explicit list of what it may not read.

## 3. Real data

Real-data sets are built from sources on the machine, with truth defined by the source and a fixed share hidden per
split: `studies/evidence_policy/confirm/realdata.py` (Round 1: Python stdlib, dist-packages, Unicode, dpkg) and
`studies/round2/confirm/realdata2.py` (Round 2: C headers, time zones, services, Python `Requires-Dist`). Both write a
manifest with source hashes and per-split counts and expose `load(name, seed) -> World`. Document provenance, truth
and independence in a `REALDATA.md` before anything runs on them.

## 4. Harness validation, pre-registration, confirmation

1. **Validate the harness without the engine on confirmation data.** Planted engines whose right answers are known
   (an oracle that asserts exactly the hidden facts; one that asserts every undeterminable fact; fabricated or missing
   proofs for the counterfactual checker) and a dry run of the confirmation script on development data. Examples:
   `studies/evidence_policy/confirm/validate_harness.py`, `studies/round2/confirm/validate_harness2.py`.
2. **Pre-register.** Hypotheses with mechanical pass criteria, the profiles, the data and seeds, the tolerances, and
   the decisions each result feeds. Hash it (`sha256sum PREREGISTRATION.md > prereg_hash.txt`) and commit before the
   run.
3. **Run it exactly as written.** `confirm2.py sealed`, `confirm2.py real`, the gate, `make test`. A crash or a
   necessary change goes in `DEVIATIONS.md` with the reason, before you look at results where possible.
4. **Report mechanically.** `confirm2_report.py --gate="..." --tests="..."` writes `RESULTS.md` (verdicts and every
   table) from the result files. Then write `CONFIRMATION.md` by hand: what passed and failed, why, and which
   pre-fixed decision follows.

## 5. The gate and the stress bench

- `studies/scaling/tools/gate.py BASE NEW`: 221 command cells, byte-compared. Compatibility evidence only: it says
  legacy didn't change, never that anything improved.
- `studies/stress/tools/bench.py catalog` then `run BINARY OUT.jsonl`: 31 real datasets, legacy output and cost.
  Needs `/usr/bin/time`.
