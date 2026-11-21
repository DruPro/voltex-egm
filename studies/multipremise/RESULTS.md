# Multi-premise study: results

Two pre-registered rounds (PREREGISTRATION.md, PREREGISTRATION_R2.md; hashes and times in
prereg_hash.txt), deviations in DEVIATIONS.md. Baseline: frozen 2.2.1 from DruPro/voltex-egm.
Gate: with every new switch at its default, byte-identical to the baseline on 22/22 datasets,
after every change. Self-test and sanitizer clean with all switches on.

## Verdicts

| Hypothesis | Round 1 | Round 2 |
|---|---|---|
| H1a lineage, CHAIN 2 infers nothing | Pass (0) | Pass |
| H1b lineage, CHAIN 3 learns great-grandparent but not great-great | **Fail**: also learned great-great (1,200/1,200) by composing its learned 3-step relation with a 2-step rule | not re-tested |
| H1c lineage, CHAIN 4 learns both, 0 wrong | Pass (1,800/1,800 and 1,200/1,200) | Pass |
| H2 hidden world: CHAIN 3/4 cost ≤ 0.01 precision | **Fail**: −0.024 / −0.238 (worst run 0.017) | **Fail**: −0.024 / −0.051 (worst run −0.26) |
| H3 company world: no precision loss | Pass | Pass (and the 26-value condition is gone) |
| H4 conditions: harvest errors −80% | **Fail**: −63%, true condition found but rejected in some runs | **Pass**: −98% (943 → 19) |
| H4 overall precision | 0.9705 | **Pass**: 0.9804 (shipped 0.9545); worst run 0.959 (shipped 0.838) |
| H4 lost correct harvests explained by unobserved professions (R2 only, ≥ 80%) | — | **Fail**: 62%; 13 of the rest from one spurious condition |
| H5 unchanged worlds, all options on | Pass | Pass |
| H6 cost on 5,828 facts (exploratory) | mining 0.12 / 0.42 / 1.43 s, inference 0.09 / 0.29 / 0.91 s at CHAIN 2 / 3 / 4 | — |

## What was learned

**Longer chains work where the world is chain-shaped, and hurt where coincidences are
plentiful.** In the lineage world, CHAIN 3 and 4 learned great-grandparent and
great-great-grandparent from examples with no intermediate relation, inferring 3,000 links
for unseen families with 0 wrong; the shipped engine inferred none. On the company world they
never hurt, and fixed all 4 wrong facts in the two noisy datasets (1 and 3). On the hidden world they raise recall slightly
(0.489 → 0.495–0.497) but cost precision, mostly by learning the over-general harvest rule
through more routes (harvest errors 943 → 2,083 at CHAIN 3).

**The coverage correction must not apply to rules it was never validated on.** Round 1's
CHAIN 4 collapse (243,329 wrong facts) came from weak long rules being relaxed past the
acceptance bar and promoted to "law" by dividing by estimated coverage, then feeding each
other. Scoring path rules without that correction (F1) removed 98% of the wrong facts.

**Conditions recovered the hidden world's true conditional rule unprompted.** "lives in &
produces ⇒ harvests, if works as farmer or miner" was found from evidence that harvest facts
are present for farmers and miners and absent for everyone else. Two design errors had to be
fixed first, both cases of the same principle: unknown profession is not "outside the group"
(missing is not false), and a condition that lists most of a relation's values is a memorized
list, not a group.

**A remaining weakness:** with little evidence, the condition with the highest score can be a
coincidence. In one run the sibling-harvest rule was restricted to "is from kavoia" on 9
cases instead of to the profession.

**Circuits (item 4, exploratory).** A XOR world of 300 gates: no configuration learned
anything (0 right, 0 wrong) because a gate's output depends on two branches at once and a
chain follows only one. Circuits need a different rule family: tree-shaped rules joining
several branches, with constants on more than the head. The engine refused rather than guess.

**Configuration (exploratory).** See CONFIGURATION.md: settings are not saved with a
knowledge base (the same file gave 7,169 or 90 inferred facts depending on whether a setting
was re-entered), and there is no single declaration of what the settings are.

## Recommendations

1. **Ship `DEPTH`** (depth study passed; all options-on worlds unchanged here).
2. **Ship `CONDITIONS` as experimental, off by default.** It is the best configuration on the
   hidden world and harmless on the others, but a third round should test a stronger
   evidence minimum for conditions and a preference for conditions shared by several rules.
3. **Keep `CHAIN ≥ 3` experimental, off by default.** It is right for chain-shaped domains
   (lineage, containment) and costs precision in coincidence-rich ones. Next: a penalty per
   extra premise and multiple-comparison control, and letting conditions refine path rules.
4. **Fix configuration persistence first** (CONFIGURATION.md): it is a real bug and changes no
   answers.
5. **Tree-shaped rules** are the route to circuits; design them as their own study.

## Reproducing

`tools/h1_lineage.py`, `tools/h2_h4_blind.py`, `tools/x1_xor_circuit.py`, and the company-world
evaluator in the Blind World and Improvement studies. The hidden-world and company-world data
are not yet in the repository; the scripts expect them at their study paths.
