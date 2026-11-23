# Round 2 sealed worlds

`gen_sealed2.py` generates synthetic fact sets with complete, known truth, in which several rules of
different, known quality share one world (see `SPEC.md`). It was written from `SPEC.md` and the
"Usage" and "Conventions" sections of `../sealed/README.md` alone, without reading the engine, the SDK,
any development world, the Round 1 generator or any study result. Python 3 standard library only.

## Usage

    python3 gen_sealed2.py STRUCTURE SEED OUTDIR [param=value ...]   # writes facts.txt, key.json
    python3 gen_sealed2.py --check      # check() plus determinism, every structure, seeds 0..2

From Python: `lines, key = world("graded", 7, noise=[0, 0.1, 0.2, 0.4, 0.6])`.
Parameter values on the command line are parsed as JSON, e.g. `branch=[4,5,6]`. Unknown parameter
names are rejected.

Output is deterministic for a given (structure, seed, params): the RNG is seeded from the structure
name and seed only, and nothing depends on set or hash order. Lines are shuffled with that RNG, so
their order carries no information.

## Conventions

Same as Round 1: facts are `SUBJECT relation phrase OBJECT`; names are a CVC / CVCV / CVCVC / VCVC /
CVVC stem (consonants `bdfgklmnprstvz`, vowels `aeiou`, a small English blocklist) plus a 1-2 digit
suffix 1..99; relation phrases are lowercase words without digits, drawn per world from a fixed pool
(except the phrases SPEC.md names: `requires`, `suggests`, `carries`, `is under`). Truth is complete;
every truth fact is exactly one of stated, hidden, undeterminable; `corrupted` entries are
`[rel, subj, wrong_obj, right_obj]`; `unseen` is empty at the defaults.

`key.json` fields: `structure, seed, params` (defaults merged with overrides), `relations` (list of
phrases), `truth` and `hidden` (lists of `[rel, subj, obj]`), `undeterminable`, `corrupted`, `unseen`,
`rules` (generating rules in words), `conditions` (only `conditional_rare`: `{rule, relation, values}`),
and `rule_quality`.

Points that differ from or extend Round 1:

- `undeterminable` entries are `[rel, subj]` for one-value relations, as in Round 1. For many-valued
  relations (only `chain_noise` produces any) the subject does not name one fact, so entries are
  `[rel, subj, obj]`.
- `rule_quality` entries are `{rule, relation, precision}`. The rule *fires* wherever its premises are
  stated lines of facts.txt (corrupted lines included); `precision` is the share of the facts it then
  concludes that are in truth. It lists generating rules and decoys (decoys are not in `rules`).
  For `graded` entries also carry `stated_agreement`: the share of the stated conclusions that agree
  with the rule (1 - noise), since the rule itself is exact in truth.
- Hidden means derivable from facts.txt by the generating rules (for transitive relations, by repeated
  application); undeterminable means not derivable. `check()` verifies both directions by applying
  the rules to the stated lines. In `competing` only rule 1 counts as deriving (SPEC.md).
- Where a structure fixes a share (stated fraction, noise, reverse share, exception share, p_good,
  p_bad), the generator picks exactly `round(share * n)` items rather than flipping a coin per item,
  so measured rates match their parameters to rounding.

## Structures

| structure | relations | rule (generating; decoys marked) | params (defaults) | lines, seed 0 |
|---|---|---|---|---|
| `reversed_weak` | `requires`, `suggests` | `requires` transitive (precision 1); decoy `suggests(a,b) -> requires(b,a)` (precision = reverse_share) | roots=10, branch=[6,10], stated=0.7, reverse_share=0.2 | 1,740 |
| `graded` | 5 x (A_i, B_i, C_i) | A_i(x,y), B_i(y,z) -> C_i(x,z), five independent rules | n_x=200, n_y=40, n_z=20, stated=0.7, noise=[0,0.05,0.15,0.30,0.50] | 1,900 |
| `skewed` | A, B, C | A(x,y), B(y,z) -> C(x,z), exact | n_x=1200, n_y=60, n_z=25, zipf=1.2, stated_high=0.9, stated_low=0.2 | 2,235 |
| `multivalue` | A, B (many-valued), `carries` | A(x,y), B(y,z) -> carries(x,z) for every z of y | n_x=600, n_y=80, n_z=40, values=[1,5], stated=0.6 | 1,943 |
| `exceptions` | A, B, C | A(x,y), B(y,z) -> C(x,z) except exception X (precision 1 - exception_share) | n_x=1000, n_y=50, n_z=25, stated=0.7, exception_share=0.12, exception_stated=0.7 | 1,750 |
| `competing` | A1, B1, A2, B2, C | rule 1 A1,B1 -> C (p_good); rule 2 A2,B2 -> C (p_bad) | n_x=800, n_z=25, y_per_z=2, p_good=0.9, p_bad=0.55, stated=0.6 | 2,180 |
| `sparse` | 3 x (A_i, B_i, C_i), padding P | A_i, B_i -> C_i, exact, with 6 / 12 / 30 stated examples | examples=[6,12,30], stated=0.7, padding=1500, padding_entities=300 | 1,639 |
| `conditional_rare` | category, attribute, A, B, C | category(x) in qualifying and A, B -> C; decoy A, B -> C unconditioned (precision 1/12) | n_x=600, n_y=40, n_z=20, categories=12, qualifying=1, attr_values=12, stated=0.85 | 1,882 |
| `chain_noise` | `is under` | `is under` transitive (measured precision about 0.84 because of corrupted links) | roots=6, branch=[4,5,6], noise=0.1, stated=0.5 | 1,644 |
| `control_degree` | 3 random relations | none | n=500, links=700, zipf=1.0, relations=3 | 2,100 |

Details:

- `reversed_weak`: a three-level hierarchy (10 roots, 60, 600). All direct `requires` links are
  stated; 70% of the indirect (grandparent) links are stated, the rest are hidden. `suggests` has as
  many links as there are direct `requires` links; exactly `reverse_share` of them reverse a direct
  `requires` link, the rest join random pairs that are not reversed `requires` facts. `suggests` is fully
  stated and implies nothing.
- `graded`: each rule has its own entities. 70% of conclusions are stated; of the stated ones exactly
  `noise_i` are replaced by a wrong Z (`corrupted`; the right fact is hidden).
- `skewed`: Y degrees follow a Zipf weight; the first `n_y` X are spread one per Y so every Y has one.
  X attached to a Y whose degree is strictly above the median Y degree are stated at `stated_high`,
  the others at `stated_low`.
- `multivalue`: each Y has `values[0]..values[1]` distinct Zs; each `carries` fact is stated with share
  `stated`, the rest hidden.
- `exceptions`: exception X get a random Z other than the rule's prediction; stated at
  `exception_stated`, otherwise undeterminable. Non-exceptions stated at `stated`, otherwise hidden.
- `competing`: truth C(x) is drawn first. Each rule has `y_per_z` Ys per Z; for its "right" X (exactly
  p * n_x of them) A links to a Y whose B is the true Z, for the others to a Y whose B is not. 60% of C
  is stated; the rest is hidden where rule 1 is right and undeterminable where it is wrong.
- `sparse`: rule i has round(examples_i / stated) X, of which exactly examples_i are stated; padding
  is a separate relation of 1,500 random links among 300 separate entities.
- `conditional_rare`: 12 categories assigned round-robin (50 X in the qualifying one, 8.3%), and an
  irrelevant attribute with 12 values, also balanced. C holds only for qualifying X; 85% stated.
- `chain_noise`: a four-level hierarchy (6, 24, 120, 720). Exactly `noise` of the direct links are
  stated pointing to a wrong node at the true parent's level (`corrupted`). Half the indirect links are
  stated. Every unstated truth fact is hidden if it follows from the stated lines by transitivity and
  undeterminable otherwise; the right fact of a corrupted link is never derivable, so it is
  undeterminable (not hidden as in Round 1's corrupted convention).
- `control_degree`: 500 entities with Zipf weights in a random rank order shared by the three
  relations; subject and object of each link are drawn by weight. Truth equals the stated facts.

## check()

`--check` runs, for every structure at seeds 0..2: key fields; line format, names, blocklist, relation
phrases; no duplicate lines; stated lines are true or listed corruptions; one-value relations have one
value per subject; states partition truth; corrupted wrong lines are stated and false, right facts true,
unstated and hidden or undeterminable; hidden facts are derivable and undeterminable ones are not;
`unseen` is correct and empty; `rule_quality` precisions equal a re-measurement and are within 0.03 of
the parameters that set them (reverse_share; 1 - noise as stated agreement; 1 - exception_share;
p_good / p_bad; qualifying / categories; 1 for exact rules); skewed stated shares within 0.03 of
stated_high / stated_low; sparse stated example counts exact; `conditions` only in `conditional_rare`;
`control_degree` has no rules, no hidden, no undeterminable; default worlds have 1,500 to 6,000 lines;
and the world is identical when rebuilt, and differs between seeds 0 and 1.
