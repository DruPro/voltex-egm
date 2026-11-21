# Noise study: results

Pre-registered 2026-11-20T19:24:33Z (`PREREGISTRATION.md`, sha256 389bd9c3…). Three deviations, D1-D3, are in
`DEVIATIONS.md`. D2 fixed an unbalanced half split in REPLICATE, and every REPLICATE row was rerun after it. All
numbers below come from the `results_*.json[l]` files. `tools/analyze.py` recomputes every verdict into
`results_verdicts.json`.

## Verdicts

| Hypothesis | Verdict | In one line |
|---|---|---|
| H1(a) coincidence errors recede with more data | **pass** | Rule errors per 1,000 fell from the smallest to the largest scale in all 10 cells. |
| H1(b) wrong facts do *not* recede on their own | **fail** (good direction) | Propagated errors also fell, by more than half in 5 of 10 cells. |
| H2(a) REPLICATE cuts tree-rule errors at 30% noise by >= 50% | **pass** | 301 to 90 wrong (-70%). |
| H2(b) REPLICATE costs <= 5% on clean worlds | **fail** | Company -0.3%, but gates with `TREES` -21% (tree gates T1: 1,319 to 849 correct, 13 wrong). |
| H2(c) with REPLICATE, rule errors recede with data | **fail** | Hidden world: rule errors per 1,000 went *up* with scale, because real correlations replicate. |
| H3(a) QUARANTINE cuts propagated errors by >= 50% | **fail** | Company 165 to 150; hidden 394 to 398. |
| H3(b) QUARANTINE changes clean worlds by <= 2% | **pass** | 0.0% on company and gates. |
| H3(c) QUARANTINE never costs > 0.5 pt precision | **fail** | With `TREES`: company 30% 0.975 to 0.939, gates 5% 0.965 to 0.936. |
| H3(d) every quarantined fact is reported | pass (by construction) | Quarantined facts are listed as conflicts and in `ASK`. |
| H4(a) VOTE removes >= 50% of wrong reports from the evidence | **pass** | Company 1,250 to 291; hidden 1,223 to 287 (3 reports, 15%). |
| H4(b) VOTE changes nothing with one report per fact | **pass** | Identical output in 20 of 20 runs. |
| H4(c) VOTE never lowers precision | **fail** | Hidden world, 5 reports, 15%: 0.980 to 0.960. |
| H4(d) with VOTE, errors fall as reports repeat | **fail** | Holds in 2 of 4 cells. |
| H5 never-seen people stay at 0 invented facts; gate 22/22 with switches off | **pass** | 0 invented in all 936 grid and VOTE runs; gate 22/22. |
| H6(a) self-tuning beats defaults on >= 4 of 6 worlds | **fail** | 3 of 6 (gates, lineage, company 30%). |
| H6(b) self-tuning recovers >= 50% of the oracle's gain | **fail** | 41% on average. |
| H6(c) tuned settings transfer to other seeds of the same world | **pass** | 87% of the gain kept. |
| H6(f) the tuner cannot read hidden truth | **pass** | 0 hidden files opened in 18 audited runs. |

**Promotion:** none of the three mechanisms meets the registered bar for becoming a default. All stay experimental
and off. The tuning kit missed its registered bar (H6(a)), so it ships as **experimental**, with the limits measured
below.

## 1. What causes errors, and does more data fix them on its own?

Every wrong inference was traced through its proof (`ASK`). *Rule* errors come from a wrong rule. *Propagation*
errors come from a correct rule fed a wrong stated fact.

| Company, `TREES 1` | People | Rule errors / 1,000 | Propagation / 1,000 | Precision | Recall |
|---|---|---|---|---|---|
| 30% noise | 220 | 29.0 | 15.6 | 0.959 | 0.665 |
| | 440 | 24.9 | 25.6 | 0.950 | 0.719 |
| | 880 | 0.0 | 7.0 | 0.993 | 0.728 |
| | 1,760 | 0.0 | 3.7 | 0.997 | 0.725 |
| 15% noise | 220 | 9.0 | 31.2 | 0.960 | 0.848 |
| | 1,760 | 0.0 | 2.4 | 0.998 | 0.876 |

- **Coincidence rules recede with data.** A coincidence rarely holds again on new entities, so its evidence stops
  growing while real rules keep gaining support. In the hidden world rule errors fell too (15% noise: 26.5 to 14.2
  per 1,000), but they stay well above zero. Those are its correlation decoys ("children usually live where a parent
  lives", 80%). They are real patterns and the engine labels them *tendency*, so more data cannot remove them.
- **Wrong facts partly recede too, which was not predicted.** In a one-value relation every derivation path is a
  vote. As data grows, more independent paths outvote the single path that runs through a wrong fact. This was
  already in the inference layer. It does not happen where no rule predicts the corrupted relation: in the hidden
  world the corrupted `lives in` facts were never flagged (0 of 166 at 30%) and propagated errors stayed flat at 3%
  noise.
- **Exploratory warning: more data can also hurt.** In the coverage sweep (hidden world, 15% noise), mean precision
  went 0.983, 0.965, 0.942 at 30/50/70% coverage, then collapsed to 0.261 at 90%. At 90% a weak tendency
  ("ancestor of & sibling of => parent of", agreement 0.41) clears the rate bar (0.40 >= 0.40). Its outputs then feed
  other rules. In 2 of 3 seeds this gives 41,000-51,000 derived facts at precision 0.02. Seed 2, where the tendency
  is not accepted, stays at 0.74. Noise does not matter: the same seeds cascade at 3% noise
  (`results_coverage_cascade.json`). It is a pre-existing weakness, tendency conclusions used as premises, and it is
  the clearest next problem to study.

## 2. REPLICATE (induction): helps tree rules on small noisy data, costs too much otherwise

- With `TREES 1` at 30% noise it removed 70% of the wrong inferences (301 to 90), and all of them at the two smallest
  scales.
- It splits each rule's evidence in half, so specific rules with modest support fail one half. On clean gate data it
  rejected parts of the truth tables. The remaining partial set gave 13 wrong outputs and 470 fewer correct ones
  (1,319 to 849). Adders: 1,700 to 1,517 wires.
- **Replication tests reproducibility, not truth.** The hidden world's decoy correlations are real, so they
  replicate in both halves once the data is large. That is why H2(c) failed. Telling "strong correlation" from
  "law" needs new kinds of information, not a stricter test. This confirms a limit already on record from earlier
  studies.

## 3. QUARANTINE (evidence, fed by inference): more recall, not fewer propagated errors

| Company, 15% noise | People | Recall default | Recall QUARANTINE | Precision default | Precision QUARANTINE |
|---|---|---|---|---|---|
| | 220 | 0.807 | 0.933 | 0.980 | 0.993 |
| | 1,760 | 0.717 | 0.928 | 0.993 | 0.992 |

- Taking contradicted facts out of the evidence cleaned the statistics. Rules re-learned on that evidence were
  accepted more often and fired more often, so recall rose by up to 21 points. On noise-free worlds nothing changed.
- It did not cut propagated errors (H3(a)). The errors that propagate come from wrong facts that no two rules
  contradict, so quarantine never sees them. In the hidden world it barely fired (0-58 facts), because no law predicts
  `lives in`.
- Combined with `TREES` at high noise it made things worse (precision 0.975 to 0.939). Tree rules learned from noisy
  data contradict good facts, and quarantine then removes those good facts.
- **Layer check.** The decision lives in the evidence layer: which stated facts count. It uses inference's existing
  conflict report as input. Nothing is deleted: every quarantined fact stays visible, with the reason.

## 4. VOTE (evidence): the clearest win, when the data has repeated reports

| Company, 15% wrong per report | Precision | Recall | Wrong inferences | Wrong reports still used |
|---|---|---|---|---|
| 1 report, default / VOTE | 0.986 / 0.986 | 0.782 / 0.782 | 15 / 15 | 84 / 84 |
| 3 reports, default | 0.316 | 0.799 | 2,067 | 250 of 250 |
| 3 reports, VOTE | **0.998** | **0.954** | 2 | 58 of 250 |
| 5 reports, VOTE | 0.999 | 0.958 | 2 | 48 of 426 |

- **Repetition without voting is harmful.** With 3 reports, the default engine's precision fell to 0.32. A person
  with two stated teams makes the relation look many-valued, and inference then adds every value it is offered.
  VOTE fixes this. A value reported more often than all the others together outvotes them. A subject with no majority
  is reported as disputed and does not count against the relation being one-value.
- **Failures (H4(c), H4(d)).**
  - In the hidden world, clean evidence lets more of the decoy *tendency* rules fire. Precision went 0.980 to 0.960
    at 5 reports. With `REPLICATE` added, it was 0.983.
  - At 30% noise with 5 reports, agreeing wrong reports sometimes form a majority: 79 wrong inferences, precision
    0.936. That is still far above the default's 0.146.
  - VOTE outvoted some true facts when two wrong reports agreed: 2.8 per run in company, 9.8 in hidden at 30%.
- With one report per fact there is nothing to vote with, and the output was identical (H4(b)).

## 5. Tuning one dataset (`egm tune`)

| World | Default F0.5 | Self-tuned | External labels | Oracle | Self-tuning picked |
|---|---|---|---|---|---|
| gates (5% noise) | 0.000 | 0.696 | 0.723 | 0.726 | `TREES 1` (3 of 3) |
| lineage | 0.000 | 1.000 | 1.000 | 1.000 | `CHAIN 3` (3 of 3) |
| company, 15% noise | 0.941 | 0.941 | 0.987 | 0.986 | nothing |
| company, 30% noise | 0.886 | 0.890 | 0.925 | 0.942 | `RATE 0.3` (1 of 3) |
| hidden, coverage 50% | 0.810 | 0.810 | 0.809 | 0.810 | nothing (oracle: nothing either) |
| hidden, coverage 30% | 0.752 | 0.752 | 0.752 | 0.755 | nothing |

- **It finds structural switches.** On fresh seeds 3-5 (`results_tuning_signal.json`) it again chose `TREES 1` for
  gates and `CHAIN 3` for lineage every time. Self-tuning never scored below the defaults in 36 runs (exploratory
  count). The conservative rule (adopt only if it helps in every fold) is why.
- **It cannot see fixes for wrong facts. This is an information limit, not a bug.** It hides stated facts and asks
  for them back, and at 30% noise 30% of those facts are themselves wrong. A setting that corrects wrong facts looks
  the same as one that doesn't. Exploratory check (`results_holdout_blindness.json`, company 30%, seeds 3-5):
  QUARANTINE scored +0.0000 to +0.0006 on the holdout and +0.023 to +0.029 on the truth. Only labels from outside the
  data can show it, and with them tuning found `QUARANTINE 1` in 5 of 6 company runs.
- **External labels can overfit.** About 10% of answers were given as labels. In two hidden-world runs, label tuning
  ended slightly below the defaults (-0.0003, -0.002).
- **Settings are dataset-specific (H6(d)).** Within one world, settings carried over to other seeds (87% of the gain
  kept). Across worlds they can hurt: lineage's `CHAIN 3` on the hidden world went 0.775 to 0.636. The kit therefore
  saves settings with each knowledge base (`kb.vtx.cfg`) and never globally.
- An exploratory variant that ignored unpredictable relations when comparing settings chose exactly the same settings
  in 18 of 18 runs. It was removed: no benefit, so no extra machinery.

## Philosophy check

- **Layers.**
  - VOTE and QUARANTINE decide which stated facts count. That is the evidence layer.
  - REPLICATE is an acceptance test. That is induction.
  - Tuning sits outside the engine and only picks values for existing settings.
  - No mechanism adds logic to inference. VOTE's "disputed" subjects are an evidence annotation that inference's
    one-value test reads, the same way staleness works.
- **Nothing is deleted.** Outvoted and quarantined facts stay listed, with the reason, in `CONFLICTS` and `ASK`.
- **General, not case-fitted.**
  - Each mechanism was tested on every world, including noise-free ones.
  - The two that cost correct answers on other worlds stay off. REPLICATE cost tree gates; QUARANTINE plus `TREES`
    cost company precision. A general fix changes what it targets and leaves the rest alone; these did not.
  - VOTE's one-value test was revised twice on the dev seed and once more (D1) on an SDK test world, all before any
    confirmatory VOTE run. That is disclosed in the pre-registration and in DEVIATIONS.
- **Information limits named, not patched.**
  - Correlations that replicate.
  - Self-supervision that cannot judge noisy labels.
  - Wrong facts in relations no rule predicts.
  - Majorities of wrong reports.
- **Off switches.** Every mechanism is off by default. With all off, the gate is 22/22 identical to the previous
  engine.

## Recommendations

1. Keep all three experimental and off.
   - Turn on **VOTE** when the data repeats reports from independent sources; it was a large win there.
   - Use **QUARANTINE** for recall on noisy data whose relations are predicted by two or more rules, and not together
     with `TREES` on noisy data.
   - **REPLICATE** is not recommended.
2. Ship `egm tune` as experimental. Use it to discover structural switches. Give it verified `--labels` when the data
   is noisy, because holdout tuning cannot see denoising.
3. Next study (motivated by section 1's warning): tendency-tier conclusions used as premises compound into cascades
   at high coverage. Test confidence decay along a chain, or not chaining tendencies at all, as a fresh pre-registered
   question.
4. Pre-existing scale limit found along the way: at 4,000 gates, words left in single-word categories are not treated
   as slots. About a quarter of the "has first input" facts and half of the "is output of" facts dropped out of their
   relations, and tree inference derived nothing (`results_grid_gates.jsonl`, per_kind 800). The category layer owns
   this; it is worth its own look.

## Reproduce

```
export VOLTEX=$PWD/build/voltex2           # the engine built from this commit
cd studies/noise
python3 tools/e1_e3_grid.py company; python3 tools/e1_e3_grid.py hidden; python3 tools/e1_e3_grid.py coverage; python3 tools/e1_e3_grid.py gates
python3 tools/e4_vote.py; python3 tools/e5_side_effects.py; python3 tools/e6_tuning.py
python3 tools/e7_signal_tuning.py; python3 tools/e8_holdout_blindness.py      # exploratory
python3 tools/analyze.py
```

`e5_side_effects.py` reads the gate datasets from `/home/claude/work` (where the earlier studies ran; archived copies
are in `studies/`). Observation files are regenerated from `hidden/gen.py` if missing.

Data: the observation files (`obs.tar.xz`, 176 files) and the generator's truth cache (`hidden_cache.tar.xz`) are
packed. Unpacked, `obs/` matches `obs_sha256.txt`. The tools regenerate any missing file from `hidden/gen.py`; two
regenerated files were checked against the manifest and match.
