# Sharding done right, as an external layer

Several unchanged engines, each holding part of a company world, against one engine holding all of it. The engine
was not changed. Plan: `PREREGISTRATION.md` (sha256 and time in `prereg_hash.txt`); changes to it:
`DEVIATIONS.md`. Every number below comes from the `results_*.jsonl` files and is recomputed by `tools/analyze.py`.

## Verdicts

| ID | Claim | Verdict |
|---|---|---|
| H1 | The recipe (S4: component boundary + central stage + rule consensus) matches one engine on clean data, 122,042 facts | **PASS**, 3/3 seeds, identical answers |
| H2 | The recipe matches one engine under 15% noise, 61,108 facts | **PASS**, 3/3 seeds, identical answers |
| H3 | The boundary matters under noise | **PASS**: components + consensus kept precision 1.000; team key + consensus 0.876; team key alone 0.876 |
| H4 | Consensus matters under noise at 61,108 facts | **FAIL**: without consensus, components alone already matched (0 wrong) |
| H5 | The central stage matters for recall on clean data at 122,042 facts | **FAIL**: without it recall was the same (0.9566); answers identical |
| H6 | The recipe completes at 244,444 facts with at most 500 MB per engine and precision at least 0.999 | **PASS**: peak 254 MB (mean), precision 1.000 |
| H6b | The recipe matches one engine at 244,444 facts (one engine completed on this machine) | **PASS**, 3/3 seeds, identical answers |
| C1 | Peak memory per engine at most 25% of one engine's (122,042 facts) | **PASS**: 146 MB vs 2,129 MB (6.9%) |
| C2 | Total CPU at most one engine's (122,042 facts) | **PASS**: 10.8 s vs 12.8 s |

In short: **the right boundary is what made sharding work.** With it, every sharded arm gave answers identical to one
engine (same sha256 over the answer set) in all 15 confirmatory cells. With that boundary, the central stage never
changed an answer.
Consensus did nothing in the confirmatory cells, but was needed in an exploratory cell with more shards (below).

## Setup and integrity

- **Data:** company worlds from `studies/noise/hidden/gen.py`.
  - Clean at 122,042 and 244,444 facts; 15% noise at 61,108 facts (sizes at seed 0); seeds 0, 1, 2.
  - Noise replaces a person's team (`is on`) or city (`is based in`) with a wrong one.
- **Isolation:** the layer (`tools/shard.py`) and the engines read only `obs/`. The answer keys stay in
  `hidden/cache/` and are read only by the scorer (`studies/noise/tools/lib.py`, unchanged). I checked this:
  `shard.py` opens only the facts file it is given and its own work directory.
- **Engine:** `build/voltex2` built from `main` at `ac54dd9` (sha256 in the pre-registration), default settings
  except `MAXWORDS` sized to each engine's own input. No `[LIMIT]` line appeared in any run.
- **Machine:** 8 cores, 23 GB. Engines run one after another. CPU is user plus system time summed over every engine
  process. Memory is the largest peak resident set of any one engine process.
- **Harness gate** (`results_gate.jsonl`, seed 9): with one shard, the shard file equals the input byte for byte,
  and the answers hash identically to one engine, clean and noisy, with and without consensus.
- **Data reproduction:** the generator is deterministic. `obs_sha256.txt` and `hidden_sha256.txt` pin every file,
  and `python3 tools/run.py confirm` regenerates them.

## The layer

1. **Assign** some entities to shards; everything else is reference data.
   - **Team key** (S0, S2, S6; the scale study's split): each person goes to the shard of their stated team.
   - **Components** (S1, S3, S4, S5): connected components of `collaborates with` are packed onto shards. Then each
     unassigned entity whose `works under` neighbours all sit in one shard joins it (this places team leads). The
     noise never touches either relation.
2. **Route.** A fact goes to its subject's shard, else its object's. Reference facts go to every shard that mentions
   their subject, followed transitively in the subject direction.
3. **Central stage** (S2, S3, S4): one engine learns from all reference facts. Its law-tier conclusions are routed
   like reference facts, and its answers join the union.
4. **Consensus** (S4, S5, S6): a shard's answer survives only if the rule in its proof was accepted by more than half
   the shards, and every derived premise survives too. Proofs come from `ASK` in a second engine session per shard,
   because `INFER ALL` prints no rules.

## Results (mean over 3 seeds; sd in `results_verdicts.json`)

Clean, 122,042 facts, 8 shards:

| Arm | Precision | Recall | Wrong | CPU s | Peak MB | Identical to one engine |
|---|---|---|---|---|---|---|
| one engine | 1.000 | 0.9566 | 0 | 12.8 | 2,129 | |
| S0 team key | 0.9999 | 0.9565 | 2.3 | 4.9 | 146 | 2/3 |
| S1 components | 1.000 | 0.9566 | 0 | 4.8 | 146 | 3/3 |
| S4 recipe | 1.000 | 0.9566 | 0 | 10.8 | 146 | 3/3 |
| S5 components + consensus | 1.000 | 0.9566 | 0 | 10.7 | 146 | 3/3 |

15% noise, 61,108 facts, 4 shards:

| Arm | Precision | Recall | Wrong | CPU s | Peak MB | Identical |
|---|---|---|---|---|---|---|
| one engine | 1.000 | 0.6426 | 0 | 3.3 | 555 | |
| S0 team key | 0.876 | 0.675 | 1,911 | 2.1 | 146 | 0/3 |
| S6 team key + consensus | 0.876 | 0.670 | 1,905 | 5.1 | 124 | 0/3 |
| S1 components | 1.000 | 0.6426 | 0 | 2.0 | 146 | 3/3 |
| S4 recipe | 1.000 | 0.6426 | 0 | 4.4 | 124 | 3/3 |

S3 equals S1 in every cell: with the component boundary, the central stage changed nothing. S2 equals S0 in 5 of 6
cells. The exception is seed 0, clean, where the team key's 7 wrong answers became 0 with the central stage (not
traced).

Clean, 244,444 facts, 16 shards:

| Arm | Precision | Recall | CPU s | Peak MB | Identical |
|---|---|---|---|---|---|
| one engine | 1.000 | 0.9579 | 47.3 | 8,350 | |
| S4 recipe | 1.000 | 0.9579 | 22.7 | 254 | 3/3 |

On the scale study's 2-core, 7 GB machine, one engine hit its 6 GB address-space limit at this size. Here it completed,
in 8.35 GB. With `MAXWORDS` sized to its vocabulary (30,766 words), its precision was 1.000. The scale study's
0.573 at this size was the default 12,000-word cap, not one engine's ceiling.

## Exploratory: noise at 122,042 and 244,444 facts

Planned as exploratory (`results_explore.jsonl`). The no-consensus arms (`results_explore2.jsonl`) were added
after seeing those results; see `DEVIATIONS.md` 2.

| Facts, noise 15% | Arm | Precision (min-max) | Recall | Wrong (min-max) | Identical to one engine |
|---|---|---|---|---|---|
| 122,042, 8 shards | one engine | 1.000 | 0.6455 | 0 | |
| | S1 components | 0.9966-0.9986 | 0.6609 | 38-91 | 0/3 |
| | S4 recipe | 1.000 | 0.6455 | 0 | 3/3 |
| 244,444, 16 shards | S1 components | 0.9976-1.000 | 0.6528 | 0-128 | (no one-engine run) |
| | S4 recipe | 1.000 | 0.6455 | 0 | |

- **Consensus is needed once there are more shards.** At 8 and 16 shards under noise, components alone had up to
  128 wrong answers. Consensus removed 0 to 1,229 answers per run and left 0 wrong. The run with 0 removed is the
  one where components alone also had 0 wrong. At 122,042 facts the result was
  identical to one engine.
- **The mechanism is the one traced in the pilot.** A borderline tendency rule passes in some shards and fails in
  others, and a union keeps any shard's yes. The more shards, the more chances; that is why consensus mattered at 8
  and 16 shards and not at 4.
- **This is exploratory** (a follow-up after seeing results). It needs a fresh pre-registered test before it is
  called confirmed.

## Failures and what they mean

- **H4 failed.** At 4 shards no borderline rule split the shards, so consensus had nothing to remove. In the pilot
  (2 shards, so a majority means both) and in the exploratory cells (8 and 16 shards), it did. Consensus is cheap
  insurance whose value grows with the number of shards; it is not needed at every size.
- **H5 failed, and the scale study's recall loss did not reproduce.** With 160 teams per shard, every shard learned
  "a team is based where its department is" by itself. The central stage passed 633-649 law-tier facts per run at
  122,042 facts and changed no answer with the component boundary.
  - The scale study's code was lost, so its routing can't be compared directly.
  - It is plausible that its shards lacked the department facts. Here routing pulls them into every shard that
    mentions a team. Not tested.
  - The central stage stays in the recipe as optional: it is harmless here, and it should matter when a shard holds
    too few reference entities to learn their rules. That case was not tested.
- **The team key is not only a noise problem.** On clean data, S0 had 7 wrong answers on seed 0 (within the match
  tolerance).

## Costs

- **Consensus runs each shard twice.** Its CPU went from 4.8 s to 10.8 s at 122,042 facts. The cause is in the
  engine interface: there is no bulk command that prints the rule behind every derived fact. `INFER` without `ALL`
  prints 10 facts; `INFER ALL` prints facts without rules. So the layer issues one `ASK` per derived
  (subject, relation).
  - A rule column on `INFER ALL`'s `FACT` lines would remove the second session. That is a core change, so it is the
    owner's decision; it is reported here, not made.
- **Even so, the recipe used less CPU than one engine:** 10.8 s vs 12.8 s at 122,042 facts, and 22.7 s vs 47.3 s at
  244,444. One engine's cost grows faster than linearly with facts.
- **Peak memory per engine stayed flat** at about 150-250 MB from 61,108 to 244,444 facts. One engine grew from
  555 MB to 8,350 MB.

## Limitations

- **One world shape.** All results come from the company world, where a clean relation (`collaborates with`) lines
  up with the structure. The recipe needs such a boundary, and choosing it needs knowledge of the data: which
  relations noise can't corrupt. Without one, sharding loses precision, as S0 shows.
- **Not tested here:**
  - other worlds;
  - a real dataset;
  - a stated id or source field as the boundary;
  - parallel execution (the engines ran one after another).
- **Pilot and design order.** Pilots on seed 9 shaped the design before pre-registration, and consensus was designed
  after a pilot failure. The confirmatory seeds and sizes were fresh.

## Next

- **Pre-register consensus at 8 or more shards under noise,** to confirm the exploratory finding.
- **Test the central stage where it should matter:** many small shards, each holding too few teams to learn the team
  rule.
- **Owner's decision:** a rule column on `INFER ALL` output, and whether an `egm.shard` helper joins the SDK.

## Files

- `tools/shard.py`: the layer.
- `tools/run.py`: the harness (parts `gate`, `smoke`, `confirm`, `explore`, `explore2`).
- `tools/analyze.py`: the verdicts.
- `results_*.jsonl` and `results_verdicts.json`: the results.
- `logs/`: run output.
