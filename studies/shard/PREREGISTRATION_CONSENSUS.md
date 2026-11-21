# Pre-registration: rule consensus at 8 or more shards under noise

Written 2026-11-21, before any run below. sha256 and time in `prereg_hash_consensus.txt`. Changes go in
`DEVIATIONS.md` under "Consensus test".

## Where this comes from

In the first shard study's exploratory cells (`results_explore*.jsonl`, seeds 0-2, 15% noise), the component
boundary alone (S1) had 38-91 wrong answers at 122,042 facts (8 shards) and 0-128 at 244,444 (16 shards). With rule
consensus added (S5), there were 0 wrong, and at 122,042 facts the answers were identical to one engine.

The mechanism, traced in the pilot: a borderline tendency rule passes in some shards and not in others, and a union of
answers keeps every shard's yes. That was a follow-up after seeing results, so it is exploratory. This is its fresh
test.

## Unchanged from the first study

`tools/shard.py`, `tools/run.py` (`one()`), the scorer, `MAXWORDS` sizing, the boundaries and the match criterion
(precision >= single - 0.001, recall >= 0.99 x single). Arms:

- **single:** one engine.
- **S1:** component boundary, no central stage, no consensus.
- **S5:** S1 plus consensus.

New seeds: 3, 4, 5. None of them has been run before at any size.

## Cells

| Cell | Facts (scale) | Noise | Shards | Purpose |
|---|---|---|---|---|
| A | scale 32 (about 122,000) | 0.15 | 8 | the exploratory finding, fresh seeds |
| B | scale 64 (about 244,000) | 0.15 | 16 | more shards |
| C | scale 16 (about 61,000) | 0.15 | 8 | same shard count, smaller shards (80 teams each) |
| D | scale 32 | 0 | 8 | control: consensus must not change clean answers |

## Hypotheses

| ID | Claim | Pass if |
|---|---|---|
| K1 | Consensus makes many-shard answers match one engine under noise. | S5 meets the match criterion on every seed in cells A, B and C (9 runs). |
| K2 | Without consensus, many shards lose precision under noise. | S1 fails the precision part on at least 2 of 3 seeds in cell A, and on at least 2 of 3 in cell B. |
| K3 | Consensus is harmless on clean data. | In cell D, S5's answers are identical (answer sha256) to one engine's on every seed. |

Expected but not tested: with smaller shards (cell C), S1 loses more precision than at 4 shards on the same data.
That comparison is descriptive.

Costs (CPU, peak memory, answers dropped by consensus) are reported, with no threshold.

## What a result means

- **K1 and K2 pass:** consensus is confirmed as needed at 8+ shards under noise, and `docs/DATA_DESIGN.md` 5.3 drops
  the "exploratory" label for step 3.
- **K1 fails:** the recipe does not match one engine at that size, and the failure is reported with its cause.
- **K2 fails:** consensus was not needed on these seeds, and step 3 stays described as insurance.
