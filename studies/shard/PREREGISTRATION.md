# Pre-registration: sharding done right, as an external layer

Written 2026-11-20, before any confirmatory run. Its sha256 and timestamp are in `prereg_hash.txt`. Every later change
to this plan goes in `DEVIATIONS.md`.

## Question

Can several unchanged engines, each holding a part of the data, give the same answers as one engine holding all of
it? The scale study's sharding failed this in two ways: a split on a noisy key (team membership) put people in the
wrong shard, and a rule about shared reference data was not learned from any shard.

No engine change. Engine: `src/voltex2.cpp` sha256 `75455ec9...c020`, built binary `build/voltex2` sha256
`443b7a46...8551`, repo `main` at `ac54dd9`. The layer is `tools/shard.py`. It reads only the facts file.

## What was done before this plan (pilots, exploratory)

All pilots used seed 9, which is not a confirmatory seed, at 7,589 and 30,605 facts.

- **Harness gate** (`results_gate.jsonl`). With one shard, the shard file equals the input byte for byte, and the
  answers hash identically to one engine, clean and at 15% noise, with and without consensus.
- **Smoke test** (`results_smoke.jsonl`, 30,605 facts, 2 shards):
  - **Clean:** every arm equals one engine.
  - **15% noise:** one engine had precision 1.000. The team split (S0) had 0.920, which reproduces the scale study's
    failure. The component split (S1) had 0.994, with 38 wrong.
- **The 38 wrong answers were traced to one cause:** one rule (`works under & is based in => is based in`, tendency
  tier, agreement 0.80) was accepted by one shard and rejected by the other shard and by one engine. A union of
  answers keeps whatever any shard accepted, so each extra shard is another chance to accept a borderline rule.
- **Rule consensus was designed in response,** so it is a design made after seeing a failure. Its pilot (S4, S5)
  matched one engine exactly on that seed. The confirmatory runs below are its first fresh test.
- **The central stage had no effect in the pilot.** Each shard there held 160 teams, the same per-shard size as here,
  so the scale study's recall loss did not appear.

## The layer (frozen)

**Facts.** A fact is `subject relation words object`, with one-word names. A fact goes to the shard of its subject,
else of its object. If neither endpoint is assigned, it is a reference fact. A reference fact goes to every shard
that mentions its subject, and routing it makes its object mentioned, repeated to a fixed point (subject direction
only).

**Boundaries:**
- **key:** each subject of `is on` goes to the shard of its majority stated team. Teams are dealt round-robin in
  name order. This is the scale study's split; the noise corrupts `is on`.
- **components:** connected components of the `collaborates with` graph are packed largest first onto the
  least-loaded shard. Then one attach pass: an unassigned entity joins a shard if all its assigned `works under`
  neighbours are in that one shard. The noise model never corrupts `collaborates with` or `works under`.

**Central stage.** One engine learns from all reference facts. Its law-tier conclusions are added to the reference
facts before routing, and all its answers join the union.

**Consensus.** A shard's answer is kept only if the rule in its proof was accepted (an `ACCEPT` line in
`RELATIONS`) by a strict majority of shards (more than n/2), and every derived premise of its proof is kept too.
Proofs come from one `ASK subject relation ?` per derived (subject, relation), in a second session per shard.

**Arms:**

| Arm | Boundary | Central | Consensus |
|---|---|---|---|
| single | none (one engine) | | |
| S0 | key | no | no |
| S1 | components | no | no |
| S2 | key | yes | no |
| S3 | components | yes | no |
| **S4** (the recipe) | components | yes | yes |
| S5 | components | no | yes |
| S6 | key | no | yes |

**Run details:**
- **Settings:** defaults for every engine, except `MAXWORDS = max(12000, distinct words in that engine's input +
  1000)`, so no engine silently drops words. Any `[LIMIT]` line is counted and reported.
- **Shard count:** teams / 160, as in the scale study: 4 shards at 61,108 facts, 8 at 122,042, 16 at 244,444.
- **Execution:** engines run one after another on one machine (8 cores, 23 GB; the scale study used 2 cores and
  7 GB, so timings are not comparable with it). Peak memory is the largest peak resident set (`wait4`) of any one
  engine process. CPU is user plus system time summed over all engine processes.
- **Memory guard:** one engine is stopped above 18 GB resident and counted as not completed.

## Data and scoring

- **Worlds:** company worlds from `studies/noise/hidden/gen.py` (`company(seed, scale, noise)`).
  - Clean at scale 32 (122,042 facts at seed 0) and scale 64 (244,444 at seed 0).
  - 15% noise at scale 16 (61,108 at seed 0).
  - Confirmatory seeds: 0, 1, 2.
- **Answer keys:** hidden truth lives in `hidden/cache/`. The layer and the engines see only `obs/`.
- **Scoring:** `studies/noise/tools/lib.py` `score()`, unchanged. Precision is correct new facts over all new facts.
  Recall is correct new facts over true facts that were not stated. The sharded answer is the union.

**Match criterion,** per seed: precision >= single's precision - 0.001, and recall >= 0.99 x single's recall.

## Hypotheses (confirmatory)

A hypothesis about "every seed" passes only if it holds on all three seeds.

| ID | Claim | Pass if |
|---|---|---|
| H1 | The recipe matches one engine on clean data at 122,042 facts. | S4 meets the match criterion on every seed (scale 32, clean). |
| H2 | The recipe matches one engine under 15% noise at 61,108 facts. | S4 meets the match criterion on every seed (scale 16, noise 0.15). |
| H3 | The boundary matters under noise. | At scale 16 and 15% noise: S5 meets the precision part on every seed, S6 fails it on at least 2 of 3, and S0 fails it on at least 2 of 3. |
| H4 | Consensus matters under noise. | At scale 16 and 15% noise: S3 fails the precision part on at least 2 of 3 seeds. |
| H5 | The central stage matters for recall on clean data at 122,042 facts. | At scale 32 clean: S5 fails the recall part on at least 2 of 3 seeds, while S4 passes it on every seed. |
| H6 | The recipe scales past one engine's cheap range. | At scale 64 clean: S4 completes on every seed, with peak memory per engine <= 500 MB and precision >= 0.999. |
| H6b | (Secondary; applies only if one engine completes under the 18 GB guard.) | S4 meets the match criterion against single at scale 64 on every seed. |
| C1 | Memory saving. | At scale 32 clean: S4 peak memory per engine <= 25% of single's, every seed. |
| C2 | CPU cost. | At scale 32 clean: S4 total CPU <= single's CPU, every seed. |

**Prediction honesty:**
- H5 is genuinely uncertain. The pilot showed no central effect at 160 teams per shard, and the scale study reported
  one. A failure of H5 means the central stage is not needed with this routing, not that the recipe fails.
- C2 may fail, because consensus runs each shard twice.

## Exploratory (not confirmatory)

- 122,042 facts with 15% noise: single and S4.
- 244,444 facts with 15% noise: S4 only.
- Anything examined after the confirmatory results.

## What would change the recommendation

- **If H1 and H2 pass,** S4 becomes the scaling recipe in `docs/DATA_DESIGN.md`, with the conditions it was shown
  under: a boundary relation the user knows is clean, and company-world-shaped data.
- **If H1 or H2 fails,** the failure is reported with its traced cause, and anything tried afterwards is exploratory.
- **An `egm.shard` helper** in the SDK needs the owner's agreement, whatever the result.
