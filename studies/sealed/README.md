# Sealed confirmation worlds

`gen_sealed.py` generates synthetic fact sets with complete, known truth, for
testing the engine only after its design is frozen. It was written from a
written specification alone, without reading any development world, existing
generator or engine source.

## Usage

    python3 gen_sealed.py STRUCTURE SEED OUTDIR [param=value ...]   # writes facts.txt, key.json
    python3 gen_sealed.py --check      # check() plus a determinism test for every structure, seeds 0..2

From Python: `lines, key = world("conditional", 7, qualifying=3)`.
Parameter values on the command line are parsed as JSON, e.g. `branch=[2,4]`.

Output is deterministic for a given (structure, seed, params). Lines are
shuffled with a seeded RNG, so their order carries no information.

## Conventions

- Facts look like `SUBJECT relation phrase OBJECT`. Subjects and objects are
  single tokens. Relation phrases are lowercase words with no digits, and each
  is always written the same way.
- Entity names are pronounceable but meaningless: a stem built from one of the
  templates CVC, CVCV, CVCVC, VCVC or CVVC, followed by one or two digits (e.g.
  `ruvo3`, `ekab71`). A small blocklist rejects common English stems. Every
  name has a digit, so it can never be an English word or clash with a
  relation word. Names say nothing about an entity's role.
- **Truth is complete.** Every true fact of the world is in `key.truth`. For a
  relation the world defines, a fact that is not in truth is false. For
  example, in `conditional`, `is assigned` is false for every non-qualifying X.
- Each truth fact is in exactly one state:
  - **stated**: a line in facts.txt.
  - **hidden**: not in facts.txt, but it follows from facts.txt through the
    world's rules.
  - **undeterminable**: not in facts.txt and it does not follow from it.
    Listed as `[relation, subject]`.
- **corrupted**: a stated line that is deliberately wrong, given as
  `[rel, subj, wrong_obj, right_obj]`. The wrong line is not in truth. The
  right fact is in truth and in hidden, since the rule still determines it.
- **unseen**: entities that appear in truth but never in facts.txt. This list
  is empty for all the default structures.
- `rules` describes each generating rule in words. `conditions` is filled only
  for `conditional` and `conditional_decoy`.
- `hide` is the fraction of derivable conclusions left out of facts.txt
  (default 0.3). Some structures use `stated` instead, which is the fraction of
  conclusions that is stated.

## Structures

Line counts below are for the default parameters at seed 0.

| structure | relations | rule / truth definition | params (defaults) | lines |
|---|---|---|---|---|
| `inverse` | `is served by`, `serves` | X `is served by` Y iff Y `serves` X. Every `is served by` fact is stated. 70% of `serves` is stated; the rest is hidden. | n_clients=400, n_desks=120, min_links=2, max_links=4, hide=0.3 | 2089 |
| `symmetric` | `is paired with` | Symmetric relation. One direction is stated for every pair, and the reverse for 70% of pairs. The other reverses are hidden. | n_entities=500, n_pairs=1200, hide=0.3 | 2040 |
| `transitive` | `is within` | Four-level hierarchy: item < place < region < zone. `is within` is transitive. All direct links are stated, plus 70% of the indirect ones (item->region, item->zone, place->zone). The remaining indirect links are hidden. | n_zones=5, regions_per=[3,5], places_per=[4,6], items_per=[5,7], hide=0.3 | 1530 |
| `composition` | `is attached to`, `is housed in`, `is stationed in` | X attached to Y, and Y housed in Z, gives X stationed in Z. Each X has one Y and each Y has one Z, so `is stationed in` has one value per X. All A and B facts are stated; C is stated for 70% of X and hidden for the rest. | n_x=800, n_y=100, n_z=15, hide=0.3 | 1460 |
| `path3` | `is sponsor of`, `is great sponsor of` | A(x,y), A(y,z) and A(z,w) give D(x,w). Each family is a four-generation tree from one root, so D links the root to each generation-3 member. D examples appear only in an `example_families` fraction of families, and within those 70% are stated. Every other D fact, including all D facts of the other families, is hidden. | n_families=60, branch=[2,3], example_families=0.5, hide=0.3 | 1836 |
| `conditional` | `is classed` (K), `operates` (A), `is filed under` (B), `is assigned` (C) | A(x,y) and B(y,z) give C(x,z), but **only** when K(x) is one of the qualifying values. C is stated for a `stated` fraction of qualifying X and hidden for the rest. C is false, and never stated, for non-qualifying X. `qualifying` is either a count (that many categories are drawn by the seed) or an explicit list of category tokens. The condition is recorded in `conditions`. | n_x=1000, n_y=80, n_z=12, n_categories=8, qualifying=2, stated=0.85 | 2290 |
| `conditional_control` | same as conditional | Same shape, but the rule holds for **every** X. C is stated for 85% of X. K is present but irrelevant, and `conditions` is empty. The correct behaviour is to learn the rule for everyone, with no condition. | same as conditional | 2930 |
| `conditional_decoy` | conditional's relations plus `is tagged`, `is banded`, `is keyed` | Same as conditional, with three extra attribute relations of 6 values each. Two are uniform random. The third, chosen by the seed, gives one value to about `decoy_share` (60%) of qualifying X; all other X get uniform values, so about 17% hold it. That value correlates with the condition but does not cause anything. The decoy's actual shares are written in `rules`. | conditional's params plus n_decoys=3, decoy_values=6, decoy_share=0.6 | 5295 |
| `branching` | `is of kind`, `reads first`, `reads second`, `feeds`, `holds` | Each gate G has a kind token standing for and, or or xor. It reads two input wires and feeds one output wire. The output wire holds f_kind(input1, input2), and the two value tokens stand for 0 and 1. The mappings are in `rules`. Gates form a single layer, each with its own wires. Kinds and input values are all stated; output values are stated for 65% of gates and hidden for the rest. | n_gates=400, stated=0.65 | 2660 |
| `depth` | `is three steps past` (wording follows k), `is phased` | Numbers n_0..n_N are linked by n_(i+k) `is ... steps past` n_i. `is phased` has period k: each residue class has one value token. Values are given for a random `given` fraction. **Hidden** means some given member lies below in the same class, so the value can be carried up by steps of k. **Undeterminable** means no given member lies below. Upward inference is deliberately not counted, as the specification requires. | N=1500, k=3 (2..7), given=0.5 | 2248 |
| `noise` | composition's relations | The composition world, but a `noise` fraction of the stated C facts has a wrong Z (a uniform draw from the other Z). These are listed in `corrupted`, and the right facts are in hidden. | composition's params plus noise=0.15 | 1460 |
| `control` | `is linked to`, `is flagged by`, `is routed to` | Random distinct links with no rule. Truth is exactly the stated facts; hidden and undeterminable are empty. | n_entities=400, links_per_relation=800 | 2400 |
| `hub` | composition's relations | The composition world, with A and B targets drawn from Zipf weights 1/r^s. Every Y and Z still gets at least one link. With the defaults the top Y has about 400 X attached. | n_x=2000, n_y=150, n_z=20, hide=0.3, zipf=1.1 | 3550 |
| `ambiguous` | composition's relations plus `is graded` | The composition world, plus an irrelevant attribute `is graded` with `grades` values. The first `ambiguous` grade tokens are also used as entities: the first as an X, the second as a Y and the third as a Z. Each token therefore appears both as a category value and as an entity. The tokens and their roles are listed in `rules`. | composition's params plus grades=6, ambiguous=3 | 2260 |

Line counts at seeds 1 and 2 are close to these. `check()` asserts:

- tokens are well formed and there are no duplicate lines;
- every non-corrupted line is in truth, and corrupted lines are not;
- hidden facts are absent from facts.txt and are part of truth;
- `relations` lists exactly the relations used;
- truth equals the stated, hidden and undeterminable facts together;
- `unseen` is correct;
- in conditional worlds, no truth conclusion has a non-qualifying subject.
