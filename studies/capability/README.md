# Capability suite

Architecture-independent evaluation for voltex3 and later rounds. It measures what a relational inference engine
should accomplish, against each world's complete truth, through a fixed interface. It never reads an engine's rules,
tiers, inference rounds or templates, so a fundamentally different architecture, or an external engine, is scored the
same way. Resemblance to the previous engine is measured separately (the gate and stress bench: the compatibility
track) and never counts as progress.

- `tools/interface.py`: the evaluation interface and the voltex2 adapter (through the SDK).
- `tools/baselines.py`: trivial reference engines (stated only, majority value, one-hop inverse).
- `tools/cworlds.py`: the structure catalogue, built on the existing generators, with three-valued keys where the
  generator allows (true; false; not determinable from the observations).
- `tools/metrics.py`: the measures (C1, C3, C4, C5, C7 flags, C12), every rate with its counts, undefined when empty.
- `tools/metamorphic.py`: C9 consistency transforms (rename, shuffle, duplicate, distract) and their comparison.
- `tools/profile.py`: runs every profile on every world over seeds; writes `baseline/profile.json` and `BASELINE.md`.

```
make                                          # build/voltex2
python3 studies/capability/tools/profile.py   # about 90 s for 10 worlds x 5 seeds
python3 studies/capability/tools/profile.py --report   # rewrite BASELINE.md from the results file
```

## The capabilities

| # | Capability | Measured here |
|---|---|---|
| C1 | Retention | yes: 150 stated facts probed per run |
| C2 | Structural discovery | not yet: needs per-rule labels in the generators |
| C3 | Deduction | yes, per structure (not yet per proof depth) |
| C4 | Abstention | invented facts about unseen entities; undeterminable queries answered (`remainders` labelled) |
| C5 | Calibration and selectivity | yes: AURC over the engine's own ranking; precision at 50% recall |
| C6 | Incomplete evidence | partly: three `hidden` coverage levels |
| C7 | Noisy and conflicting evidence | flags on injected corruptions; `company-noise15` |
| C8 | Generalization | renamed vocabulary only (in C9) |
| C9 | Consistency | yes: rename, shuffle, duplicate, distract, determinism |
| C10 | Explanation fidelity | not yet |
| C11 | Change | not yet |
| C12 | Cost and scaling | seconds and peak memory per run (no scaling fits yet) |
| C13 | Active verification | not yet: Investigation V's verification world |

## Rules

- A rate with nothing to divide by is undefined, never 1.0.
- A change is judged on its worst structure as well as its mean (the "Worst structure" table).
- `egm-matched` uses each structure's own setting and is labelled as tuned per structure.
- Trivial baselines are given the relation phrases; EGM must discover them. Reported with every profile.
