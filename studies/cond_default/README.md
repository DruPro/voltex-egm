# CONDITIONS 1 as the default: before and after

On 2026-11-23 the owner made `CONDITIONS 1` the default, as Round 2's confirmation recommended (H6 passed:
`studies/round2/CONFIRMATION.md`). This folder records what changed: compatibility, capability metrics on every
world set the project has, and performance on the stress bench.

**Before** is the previous engine (`main` at `9817deb`; for the metrics, `SET CONDITIONS 0` on the new binary, which
the gate shows is output-identical). **After** is the new default (`27fde74`). The setting is also no longer marked
experimental.

## Compatibility

| Check | Result |
|---|---|
| New default vs previous engine (gate, 221 cells) | 193 identical. **Content** changes only in `harvest` (11 cells), the gate's world with a group condition. The other 17 are the cells that already set `CONDITIONS 1`: identical apart from `[CONFIG]` notices (the setting is no longer listed as experimental, nor saved in `.cfg` since 1 is the default). `gate_new_default.json` |
| `SET CONDITIONS 0` vs previous engine | 204 byte-identical. The same 17 cells differ only in those notices. So `CONDITIONS 0` restores the previous behaviour exactly. `gate_conditions0.json` |
| Unit tests | 91 OK, after updating two tests that encoded the old default (`tests/test_sdk.py`) |
| Saved knowledge bases | `.cfg` stores only settings that differ from the default, so a knowledge base saved before this change reloads **with** conditions on. `SET CONDITIONS 0` after `LOAD` keeps the old behaviour. |
| `REFRESH` | its fast path never applies with conditions on; `REFRESH` is itself off by default, so the default engine is unaffected, and users of `REFRESH` need `SET CONDITIONS 0` |

## Capability metrics (`before_after.py`, `REPORT.md`)

Default, strict and tendency profiles, 210 world-seed runs. On the dpkg-like `reversed_weak` world, only the default
profile runs, because the old profiles flood it at 100 to 600 seconds per run.

| World set | Worlds changed | Precision | Recall | Wrong answers (sum of means), default profile |
|---|---|---|---|---|
| Development worlds (10 × 5 seeds) | 3 of 10 | up in all 3 | −0.002 on two `hidden` worlds | 931 → 149 |
| Round 1 sealed (14 × 5) | 2 of 14 (`conditional`, `conditional_decoy`) | 0.047 → 1.000, 0.048 → 1.000 | unchanged (1.0) | 1,502 → 0 |
| Round 2 sealed (10 × 5) | 1 of 10 (`conditional_rare`) | 0.014 → 1.000 | unchanged (1.0) | 550 → 0 on that world |
| Real data, Round 1 sets (4 × 5 splits) | 0 of 4 | unchanged | unchanged | unchanged |
| Real data, Round 2 sets (4 × 5 splits) | 0 of 4 | unchanged | unchanged | unchanged |

The three profiles move together. Strict on the development worlds is unchanged: it already excluded the
over-general `harvest` rule. Precision went down nowhere, in any profile or world.

| Changed world | Profile | Precision | Recall | New answers |
|---|---|---|---|---|
| harvest | default | 0.029 → 1.000 | 0.985 → 0.985 | 614 → 18 |
| hidden-cov70 | default | 0.915 → 0.971 | 0.568 → 0.566 | 2,025 → 1,897 |
| hidden-cov50 | default | 0.962 → 0.983 | 0.507 → 0.506 | 2,580 → 2,512 |
| conditional (Round 1 sealed) | all three | 0.047 → 1.000 | 1.000 → 1.000 | 790 → 37 |
| conditional_decoy (Round 1 sealed) | all three | 0.048 → 1.000 | 1.000 → 1.000 | 787 → 38 |
| conditional_rare (Round 2 sealed) | all three | 0.014 → 1.000 | 1.000 → 1.000 | 558 → 8 |

## Stress bench: 31 datasets, 295 cells (`bench_before.jsonl`, `bench_after.jsonl`, `bench_compare.txt`)

The bench scores against its own held-out keys at the engine's default settings.

| | Before | After |
|---|---|---|
| Cells with changed content | — | 29: harvest and three real code datasets |
| Precision on changed cells with a key (20) | — | up in 20, down in 0; recall down in 0 |
| `code_py_stdlib`, default | precision 0.015, recall 0.089, 28,123 new | precision **0.810**, recall 0.089, 521 new |
| `code_py_dist`, default | precision 0.0095, recall 0.067, 41,800 new | precision **0.527**, recall 0.067, 757 new |
| `code_mixed`, default | precision 0.014, recall 0.040, 23,727 new | precision **0.375**, recall 0.040, 910 new |
| Wrong answers summed over the 29 cells | ~680,000 | 5,961 |

The Round 1 real-data sets built from the same Python code show no change. That protocol sets `MAXWORDS` to cover
every word, which gives different categories, and no condition was learned there. Both are reported as measured.

## Performance

| Measure | Before | After |
|---|---|---|
| Stress bench, total time (295 cells) | 566.0 s | 566.0 s |
| Incremental-update cells (31) | 117.5 s | 118.8 s |
| Peak memory per cell | — | median ×1.00, max ×1.05 |
| Cells whose output didn't change (79 over 0.5 s) | — | median ×1.04: the condition search runs and finds nothing |
| Large unchanged worlds, 3 alternating runs | `gen_company32` 9.62 s, `gen_hidden8` 6.68 s | 10.16 s (×1.056), 7.02 s (×1.051) |
| Cells where conditions removed a flood (30) | — | median ×0.71: fewer answers to produce |
| World runs in `before_after.py` (sum of means) | default: dev 1.7 s, Round 1 sealed 0.9 s, real 48.4 s | 1.6 s, 0.7 s, 47.5 s |

The cost of the new default is about 5% more learning time on data where no condition applies. Where conditions do
apply, they are faster, because they stop floods.
