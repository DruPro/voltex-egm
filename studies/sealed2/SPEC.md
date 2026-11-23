# Round 2 sealed generator: specification

Written before the generator exists. The generator is written by a separate agent from this file and from the
output format in `studies/sealed/README.md` (sections "Usage" and "Conventions" only). The agent does not read the
engine (`src/`), the SDK (`egm/`), any development world, `studies/sealed/gen_sealed.py`, or any study result.

## Purpose

Round 1's sealed worlds could not tell rankings apart: in most structures every reasonable rule was right, so every
ordering of answers scored the same. These worlds put **several rules of different, known quality** into one world,
so an engine that orders its answers by real reliability scores better than one that does not.

## Output contract (same as Round 1, so the existing harness reads it)

`gen_sealed2.py STRUCTURE SEED OUTDIR [key=value ...]` writes `facts.txt` and `key.json`; `--check` self-checks every
structure at seeds 0..2 and tests determinism. `world(structure, seed, **params) -> (lines, key)`.
`key.json` has exactly the fields of Round 1: `structure, seed, params, relations, truth, hidden, undeterminable,
corrupted, unseen, rules, conditions`, with the same meanings, plus one new optional field:

- `rule_quality`: a list of `{"rule": text, "relation": conclusion relation, "precision": p}`, the true precision
  of each generating or decoy rule over the subjects it fires on, measured on the generated world.

Names, tokens, relation phrases, truth completeness and the three states (stated, hidden, undeterminable) follow
the Round 1 conventions. Line order is shuffled with the seed.

## Structures (defaults chosen so each world has 1,500 to 6,000 lines)

1. `reversed_weak`: a one-value-per-subject relation `requires` built as a three-level transitive hierarchy
   (stated 70%, rest hidden), plus a second relation `suggests` where `suggests(a,b)` holds for a random 20%
   (param `reverse_share`) of pairs with `requires(b,a)` and otherwise links random pairs. `suggests` is fully
   stated. Truth for `requires` is the hierarchy; `suggests` implies nothing.
2. `graded`: five independent composition rules (A_i(x,y), B_i(y,z) gives C_i(x,z), one value per x) in one world,
   with distinct relation phrases, whose stated conclusions carry noise 0, 0.05, 0.15, 0.30 and 0.50 (param
   `noise` list). Noisy stated lines are `corrupted`; the right fact is hidden.
3. `skewed`: a composition rule whose conclusion is stated mostly for high-degree Y (attached Xs above the median
   Y degree: stated 90%; below: stated 20%), so the stated examples are not a random sample of where the rule
   fires. The rule is exact in truth.
4. `multivalue`: X has 1 to 5 values of `carries` (param range), derived from A(x,y), B(y,z) with B many-valued.
   Stated 60% per fact.
5. `exceptions`: an exact composition rule except for a random `exception_share` (0.12) of X, whose conclusion is a
   different, random Z. Nothing in the facts identifies the exceptions. For exceptions the true fact is stated with
   probability 0.7 and otherwise **undeterminable**; the rule's prediction for them is false.
6. `competing`: two rules conclude the same one-value relation. Rule 1 (via relations A1, B1) agrees with truth for
   90% of X (param `p_good`); rule 2 (via A2, B2) for 55% (`p_bad`). Truth is built first; each rule's middle links
   are then set so its prediction matches truth at its rate. Conclusion stated 60%; the rest hidden only where
   rule 1 is right, otherwise undeterminable.
7. `sparse`: three exact composition rules with 6, 12 and 30 examples (param list), in a world padded with an
   unrelated random relation of 1,500 links. Stated 70%.
8. `conditional_rare`: like Round 1's `conditional`, but one qualifying category out of 12 (about 8% of X), and an
   irrelevant second attribute of 12 values. C stated 85% for qualifying X.
9. `chain_noise`: four-level transitive `is under` where a `noise` (0.1) fraction of stated direct links point to a
   wrong parent (`corrupted`); truth uses the right parents. Stated indirect links 50%.
10. `control_degree`: no rules. Three random relations whose link counts per entity follow a shared Zipf
    degree (entities busy in one are busy in all), to tempt spurious correlations. Truth equals the stated facts.

Every structure lists its rules in `rules` and their measured precision in `rule_quality`; `conditions` is filled
only for `conditional_rare`. `check()` asserts the Round 1 invariants plus: `rule_quality` precisions are within
0.03 of the parameters that set them, and in `control_degree` hidden and undeterminable are empty.
