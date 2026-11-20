# Voltex EGM: Principles and Theory

*A developer's textbook on Evidential Grammar Memory: what each component is for, why the
emergent behaviors arise, and where the limits come from.*

This document explains *why* the system behaves as it does. For *how to use it*, see the
README, `docs/SDK.md` and `docs/MCP.md`. For the measurements behind every claim here, see
the papers in `docs/papers/`. Numbers quoted below are taken from those papers or from
reruns of the shipped engine, and each is marked with its source.

---

## Contents

1. The one-sentence architecture
2. Foundations: six ideas everything rests on
3. The layers, from bytes to beliefs
4. A worked example, end to end
5. A taxonomy of emergent behavior
6. Programming inference by example
7. Information limits: what no version can do
8. Design principles for developers
9. Glossary
10. References

---

## 1. The one-sentence architecture

> **Voltex EGM stores every fact exactly, counts what it sees, and accepts a pattern as a
> rule only when the counts support it, then answers with the facts and rules it used.**

Everything else follows from that sentence. There are no trained weights, no gradient
descent and no embeddings. The only learned quantities are **counts**, and every
probability, category, relation and rule is **recomputed from those counts** whenever it is
needed. Ingesting a fact *is* the training.

The behaviors this produces (rule discovery, multi-step chains, refusing to invent,
calibrated confidence, noticing stale conclusions) were not programmed one by one. They
emerge from the same loop applied at different levels of structure. Section 5 classifies
them; sections 2 and 3 explain why the loop produces them.

One consequence is large enough to get its own chapter (section 6). Because the logic comes
from the evidence rather than from code, **inference can be programmed with examples**. Show
the engine enough good examples of a conclusion next to its premises, and it learns the rule
and applies it everywhere else. The quality of the examples sets the quality of the
inference.

---

## 2. Foundations: six ideas everything rests on

### 2.1 Identity before similarity

Every word is interned to an integer id, and every distinct record (sentence) is keyed by
its exact token sequence. The same text always gets the same id, found in one map lookup.

Identity is what makes *counting* possible: you can only count how often something recurs
if you can tell that two occurrences are the same thing. Note what identity does **not**
give you: similarity. Two strings one character apart get unrelated ids, exactly as they
would under a cryptographic hash. Similarity in Voltex comes from a different source,
shared contexts (2.4), never from the ids themselves.

### 2.2 Counting is the only learning

On ingest, the engine updates unigram, bigram and trigram counts over the record's words.
Nothing else is fitted. A probability such as "how likely is `calls` after
`Session_send`?" is computed at query time from those counts, using Witten–Bell
interpolation (trigram → bigram → unigram → uniform), so unseen continuations keep a
small, principled probability instead of zero.

Consequences developers should internalize:

- **Learning is exact and incremental.** One new fact changes a handful of counts.
- **Forgetting is exact too.** `RETRACT` subtracts the same counts, so a retracted fact
  leaves no trace (verified in 5 of 5 worlds, including after save and load; *Improvement
  Experiments*).
- **Everything above the counts is derived**, so it can be rebuilt, inspected and switched
  off independently.

### 2.3 Compression is learning

Records are stored in an online grammar (Sequitur): whenever a pair of adjacent symbols
appears twice anywhere, it becomes a shared rule, and a rule used only once is folded back
in. Storage is lossless and deduplicated.

The deeper point is the *Minimum Description Length* principle: the best explanation of
data is the one that describes it most briefly. A shared grammar rule shortens the
description of repeated text. A relational rule such as "a parent's parent is an ancestor"
shortens the description of thousands of facts, because they no longer need to be stated
one by one. **Finding the shortest description of the data and finding its regularities
are the same task.** That is why a counting engine can discover logic at all.

Two honest qualifications:

- As a byte compressor, the grammar is good but not best in class: 424,918 bytes of facts
  stored in 131,755 (*EGM paper*), but on JSON records xz reaches 0.57 MB where Voltex
  needs 1.28 MB (*Research & Architectural Assessment*).
- The engine currently keeps every stated fact even when a rule could regenerate it.
  Relational rules sit *on top of* storage; the compression view explains why rules are
  found, not how bytes are stored today.

### 2.4 The distributional hypothesis

Words that occur in the same contexts tend to play the same role. If `gala`, `fuji` and
`honeycrisp` all appear after `has variety` and before `has color`, they are
interchangeable in this data: they form a category. Categories are what let the engine
treat `? has color ?` as one relation instead of hundreds of unrelated sentences, and what
let it assign probability to combinations it has never seen.

### 2.5 Evidence is measured against a base rate

A pattern seen often is not yet a rule: it may be common for every subject. The engine
compares how often a rule's conclusion holds (its **rate**) with how often that conclusion
would hold for a random pair (its **base rate**). The ratio is **lift**. A rule must clear
both: frequent enough to matter, and far more frequent than chance.

### 2.6 Missing is not false (the open world)

Facts are only ever *stated*, never *denied*. If the data does not say "Ann lives in
Oslo", that may mean it is false, or only that nobody wrote it down. The engine therefore
judges rules mostly where the answer is **known** (the *partial completeness assumption*,
from the AMIE rule-mining literature): a rule predicting Ann's home is tested only on
people whose home is stated. Many of the system's limits (section 7) are this one idea
showing up in different places.

---

## 3. The layers, from bytes to beliefs

Each layer has one job, one vocabulary, and depends only on the layers below it. The first
two are stored; the rest are rebuilt from counts when queried. This separation is the most
important architectural property: a problem is fixed in the layer that owns it, never
patched in a layer above (see section 8).

```
 6  Presentation   labels, proofs, history lines, flags        (what the user sees)
 5  Evidence view  sources, time, current vs past, disagreement (what holds now)
 4  Inference      rules applied to a fixpoint, with proofs     (what follows)
 3  Induction      relations, candidate rules, scoring          (what patterns hold)
 2  Statistics     counts, categories, probabilities            (what co-occurs)
 1  Storage        tokens, exact records, grammar               (what was said)
```

### Layer 1: Storage — what was said

- **Tokenizer.** Lossless: runs of word characters (letters, digits, `_`, non-ASCII), runs
  of spaces or tabs, and single other bytes. Whitespace tokens are stored but excluded from
  everything statistical.
- **Records.** Each line becomes a record. An identical line increments the existing
  record's count instead of being stored again.
- **Grammar.** New records are appended to a Sequitur grammar, which maintains two
  invariants: no pair of adjacent symbols occurs twice, and every rule is used at least
  twice. Any record can be unrolled back to its exact text.

*Owns:* exactness, identity, deduplication. *Never* interprets meaning.

### Layer 2: Statistics — what co-occurs

- **Counts** over each record's words (section 2.2).
- **Categories.** For the most frequent words (up to 12,000), the engine builds each word's
  left-context and right-context profiles, compares them by cosine similarity, and merges
  words whose *both* profiles agree at or above 0.5. Merging is repeated for up to four
  rounds, each round comparing *categories* rather than words, so categories can grow
  through chains of similarity. A word in a category of at least two is called **open**: it
  can fill a slot.
- **Probabilities** mix a word-level model with a category-level model (half each). The
  category model is what generalizes: it can rate a word pair never seen together if their
  categories have been.

*Owns:* similarity, generalization over words, prediction and generation.

### Layer 3: Induction — what patterns hold

**Relations (templates).** For each record, the engine finds its open words (2 to 8 of
them) and considers each pair of them as the two slots of a template, holding the other
words fixed. It keeps the pair whose template is supported by the most records, provided
at least 3 records share it. `kiruki lives in sadobe` thus becomes a fact of the relation
`? lives in ?`. At most 40 relations are kept.

**Candidate rules.** Between every pair or triple of relations, the engine considers three
rule shapes:

| Shape | Form | Example |
|---|---|---|
| Inverse (or symmetric, when R = S) | R(a,b) ⇒ S(b,a) | A contains B ⇒ B is in A |
| Transitive | R(a,b) & R(b,c) ⇒ R(a,c) | A is in B, B is in C ⇒ A is in C |
| Composition | R(a,b) & S(b,c) ⇒ T(a,c) | A lives in B, B is located in C ⇒ A is from C |

**Scoring.** For each candidate:

- **n**: chains seen (premises that hold);
- **k**: chains whose conclusion is also stated;
- **rate** = k / n;
- **base rate** of the conclusion relation = stated facts / (distinct subjects × distinct
  objects);
- **lift** = rate / base rate;
- **pn** and **PCA agreement** = k / pn, counting only chains where the subject's answer in
  the conclusion relation is known.

**Acceptance.** A rule needs k ≥ 3, and then either

- the classic test: lift ≥ 5 and rate ≥ 0.4, **or**
- the known-answer test: pn ≥ 5, agreement ≥ 0.8, and agreement at least 3 standard
  deviations above what chance would give.

**Coverage awareness.** When an inverse rule is strong (lift ≥ 20, k ≥ 10), its rate
estimates how *complete* the data for that relation is: if every "contains" has its
matching "is in", nothing much is missing. The median of these estimates is the global
coverage. When coverage looks low, the rate bar is relaxed to 0.8 × coverage, **never
raised**. (The two-sided version that could also raise it was tested and rejected; see
section 8.)

**Labels.** Each rule gets a **reliability** estimate: its agreement where answers are
known, for one-value relations; otherwise its rate divided by coverage. Reliability ≥ 0.95
makes it a **law**; anything else is a **tendency**.

*Owns:* every claim of the form "this pattern holds". Nothing here is domain-specific.

### Layer 4: Inference — what follows

Accepted rules are applied repeatedly, up to four rounds, until nothing new is derived (a
fixpoint). Each derived fact records:

- its **proof**: the premise facts and the rule that combined them;
- its **score**: the rule's rate times the confidence of its premises, so uncertainty
  compounds along a chain;
- its **tier**: law only if every step was law-tier.

For **one-value relations** (at least 95% of subjects have exactly one object, such as
"lives in"), each derivation path is a *vote*. The value with the most paths wins and is
reported as "k of n paths agree". If the stated value is out-voted, the engine raises a
**contradiction**, but only if at least two *distinct* rules agree on the alternative, so
one bad rule cannot overturn a stated fact.

*Owns:* consequences, proofs, conflicts. It never decides what is current; that is layer 5.

### Layer 5: Evidence view — what holds now

`OBSERVE source record time revision scope | facts` records not just a fact but *who said
it, about what, and when*. The engine keeps an observation log and **projects** it:

- a `snapshot` is everything that record states now: facts it stopped stating become
  **history** ("held per census from t=1 until t=2");
- a `partial` only adds facts;
- only currently supported facts feed layers 3 and 4;
- two independent sources giving different values for a one-value relation are flagged
  **SOURCES DISAGREE**; a later partial update with a different value is flagged
  **UNCERTAIN**. Neither is resolved silently.
- A derived fact that followed from a fact which has since changed is flagged **STALE**,
  and the engine re-derives it through the same rule from the new facts if it can ("current,
  because …"); if it cannot, the value is reported as unknown.

The key design decision: **change is handled here, as evidence, not as special logic inside
inference.** Two earlier designs put amendment logic in the inference engine; the
source-aware evidence approach was recommended over them, and it needs no change to the
reasoning layer (*Dynamic Relational Evolution*; *Evidence Before Inference*).

### Layer 6: Presentation — what the user sees

Every answer line carries a status (stated, current, inferred, historical, corrected,
superseded, withdrawn), a flag where relevant, the tier and score for inferences, the proof,
and the source. Explanation is not a feature added at the end: it is the same data the
layers already computed, printed.

---

## 4. A worked example, end to end

The containment test world (*Research & Architectural Assessment*; rerun with the shipped
2.2.1 engine): towns contain buildings, buildings contain rooms, rooms contain people. The
engine received 486 sentences: 210 "is in" facts with half of the implied ones held back,
60 "contains" facts, and 216 "knows" facts drawn at random as a control.

**Storage and statistics.** Names like `nekalo` and `loloti` appear in the same positions
around `is in`, so they fall into categories and become open words.

**Relations.** Three templates reach the support threshold:

```
#0  ? knows ?       216 facts
#1  ? is in ?       210 facts
#2  ? contains ?    60 facts
```

**Induction.** The base rate of "is in" is 210 / (120 subjects × 52 objects) = 0.0337. The
candidate "A contains B ⇒ B is in A" holds in all 60 chains (rate 1.00), so its lift is
1.00 / 0.0337 = 29.7. It is accepted, and because it is strong and redundant it also tells
the engine the "is in" data looks complete. The engine's output:

```
ACCEPT [? contains ?](a,b) => [? is in ?](b,a)                    rate=1.00 tier=law
ACCEPT [? contains ?](a,b) & [? is in ?](b,c) => [? is in ?](a,c) rate=0.74 tier=tendency
ACCEPT [? is in ?](a,b) & [? is in ?](b,c) => [? is in ?](a,c)    rate=0.46 tier=tendency
reject [? is in ?](a,b) => [? contains ?](b,a)                    rate=0.29
```

Three lessons in four lines:

- **Direction matters.** The reverse inverse ("B is in A ⇒ A contains B") was rejected:
  "contains" is stated for only 60 of the 210 pairs, so the evidence does not support it.
- **Hidden data makes true laws look weak.** Transitivity is always true in this world, but
  with half the conclusions held back it held in only 46% of the visible chains, so it was
  honestly labelled a tendency.
- **The control produced nothing.** No rule involving "knows" was accepted.

**Inference.** 90 new facts derived; scored against the hidden truth, 90 correct, and all
90 held-back "is in" facts recovered.

---

## 5. A taxonomy of emergent behavior

"Emergent" here means a behavior that no code path implements directly: it arises from the
general loop applied to particular data. The classes below are ordered by the layer they
come from. For each: the mechanism that produces it, the evidence that it happens, and the
condition under which it fails.

### Class I — Structural (layer 1): sharing and compression

| Behavior | Mechanism | Evidence | Fails when |
|---|---|---|---|
| Repeated phrases become shared building blocks | Sequitur's digram uniqueness: a pair seen twice becomes a rule | 20,000 records: 4.06 MB raw to a 1.28 MB saved model, 293× smaller than v1 (*Assessment*) | Data has no repetition (random ids compress to nothing) |
| Exact identity and recall | Interning plus records keyed by token sequence | 20,000 of 20,000 records round-trip exactly (*Assessment*) | Never, by construction |

### Class II — Distributional (layer 2): categories and generalization over words

| Behavior | Mechanism | Evidence | Fails when |
|---|---|---|---|
| Discovers parts of speech | Recursive merging of words with matching left and right contexts | 7 of 7 true categories recovered exactly on a synthetic grammar (*Assessment*) | One word plays two roles (polysemy): its contexts blend |
| Rates combinations never seen | Category-level probabilities | Unseen adjective–noun pairs: 2.15 bits per token with categories vs 3.80 without (*Assessment*) | Categories are wrong or too coarse |
| Generates new, valid sentences | Sampling from the mixed word and category model | 65.5% of generated sentences grammatical; 35.7% grammatical and new (*Assessment*) | Sparse data: few categories form |

### Class III — Relational (layer 3, templates): structure from sentence shape

| Behavior | Mechanism | Evidence | Fails when |
|---|---|---|---|
| Recognizes relations without a schema | Pairs of open slots in templates supported by ≥ 3 records | All 5 relations learned in each code corpus, from plain lines with no schema (*Tokenomics*) | A relation has fewer than 3 facts, or its slot words never form categories (cold start) |

### Class IV — Inferential (layers 3 and 4): logic from evidence

| Behavior | Mechanism | Evidence | Fails when |
|---|---|---|---|
| Discovers logical rules (inverse, symmetric, transitive, composition) | Candidate rules scored by rate, lift and known-answer agreement | Containment world: 3 rules, 90 of 90 hidden facts, 0 wrong (section 4) | Too little of the world observed |
| Finds rules nobody designed | The same scoring finds any regularity the data implies | Hidden world: 7 valid undesigned rules (e.g. a parent's parent is an ancestor) in 5 of 5 runs, beating the hand-written oracle's recall (*Blind World*) | The regularity needs a shape it cannot express |
| Chains rules into multi-step reasoning | Fixpoint inference over its own accepted rules | Recall of hidden facts at 50% coverage: 0.966 (1 step), 0.986 (2 steps), 1.000 (3 steps); rules off: 0 facts (*Blind World*) | Below about 50% coverage before the coverage fix: 0.096 / 0.029 / 0.000 at 30% |
| Generalizes from very little about an individual | Rules learned on the many, applied to the few | People with only 2 facts ingested: 469 of their 865 hidden facts recovered, 11 wrong (*Blind World*) | The individual has no facts at all |
| Infers plausible attributes ("apples can be yellow") | Composition: has variety + has color ⇒ has color, learned from 31 examples (rate 0.87) | Claim-checker run: "Apples are yellow" supported via Golden Delicious; "Bananas are blue" supported via Blue Java (claim-checker experiment, not yet written up in a paper) | The data's variety list is incomplete or wrong |

### Class V — Epistemic (layers 3 to 6): knowing what it knows

These are the behaviors most often mistaken for "understanding". They come from keeping
evidence and conclusions separate and never discarding the difference.

| Behavior | Mechanism | Evidence | Fails when |
|---|---|---|---|
| Abstains instead of inventing | No evidence, no slot; no rule, no inference | 0 facts invented about never-seen individuals in every run (*Blind World*); "Dragonfruit is pink" → unknown | Never for absent entities; see decoys below for present ones |
| Calibrated confidence | Reliability from known-answer agreement or coverage-corrected rate; law at ≥ 0.95 | Law-tier inferences 99.3–99.8% correct, covering 84–89% of derived facts; estimates within 0.01 of the true rate for laws (*Improvement Experiments*) | Strong coincidences look like laws (section 7) |
| Estimates its own coverage | Redundancy of strong inverse rules measures completeness | Coverage-aware acceptance raised recall at 30% coverage from 0.07 to 0.94 and precision from 0.87 to 0.99 (*Improvement Experiments*) | No strong inverse pair exists to measure with |
| Detects contradictions in stated facts | Path votes in one-value relations, corroborated by ≥ 2 distinct rules | Company world: 17 of 20 planted errors found, all flags correct (*Improvement Experiments*) | Hidden world: only 1–21% detected before corroboration (*Blind World*) |
| Finds true facts its evaluators missed | Rules beyond the designed set | Sonnet + EGM: 47 true extra answers vs 3 false; F1 0.944 vs 0.820 for search against the full world (*EGM paper*) | Scored only against a key built from designed rules, where search led (0.934 vs 0.913) |

### Class VI — Temporal and evidential (layer 5): living with change

| Behavior | Mechanism | Evidence | Fails when |
|---|---|---|---|
| Distinguishes a change from an addition | Snapshot projection per source and record | With source and time, accuracy on changed facts rose from 5.1% to 83.1% for EGM (*Evidence Before Inference*) | Facts arrive without source or scope: plain ingestion can only add |
| Keeps history instead of overwriting | Superseded facts become history lines | Every changed fact reported as "held per S from t1 until t2" | — |
| Notices its own stale conclusions | Dependency trace from changed facts to derived ones, then same-rule re-derivation | 31 of 31 detectable stale facts flagged; 51 of 52 flags truly stale (*Improvement Experiments*) | The new value has no premise for the rule: reported as unknown, by design |
| Reports, rather than resolves, disagreement | One-value relations with different values from independent sources | SOURCES DISAGREE and UNCERTAIN flags | — |

### Class VII — Emergent failure modes

Failures emerge from the same loop as successes, and belong in the same taxonomy.

| Failure | Why it arises | Evidence | Mitigation |
|---|---|---|---|
| Accepts strong coincidences as rules | An 85–90% correlation passes the evidence test like a law with exceptions | Decoys accepted in 13 of 15 runs (*Blind World*) | Tendency labels; strict answering policy |
| Treats conditional rules as laws | "Only farmers harvest" cannot be expressed, so it is learned for everyone | 943 wrong facts in 3 runs (*Blind World*) | None yet: needs conditional rule shapes |
| Collapses on sparse data | Rates measured against what is stated fall below the bar | 2 of 13 rules found at 30% coverage (*Blind World*) | Lower-only coverage-aware acceptance |
| Plain ingestion cannot express change | Counts only grow; "new" looks like "also true" | 5.1% accuracy on changed facts without enrichment (*Evidence Before Inference*) | Source-aware observations (layer 5) |

### How the classes relate

The classes form a ladder, and each rung depends on the ones below:

```
VI  Temporal     needs   V   (what is current depends on knowing what is supported)
V   Epistemic    needs   IV  (confidence is a property of rules and proofs)
IV  Inferential  needs   III (rules relate relations)
III Relational   needs   II  (slots need categories)
II  Distributional needs I   (contexts need identity and counts)
```

A failure low on the ladder propagates upward. When a high-level behavior misbehaves,
diagnose from the bottom: does the relation exist? Did the slot words form categories? Is
there enough evidence for the rule?

---

## 6. Programming inference by example

In most systems, an inference is something a developer writes: a rule in a rules engine, a
query in a database, a function in code. In Voltex EGM it is something you **show**. Give the
engine examples of a conclusion alongside the facts that lead to it, and it decides from the
evidence whether a general rule explains them. If one does, that rule now computes the
conclusion for every case the examples didn't cover.

This turns the usual relationship around. **The data is the program, and the examples are
its source code.** Better examples produce better inference; poor examples produce no
inference at all, rather than wrong inference.

### 6.1 A demonstration: teaching "grandparent"

Nothing in the engine knows what a grandparent is. The experiment (scripts in
`examples/programming_by_example/`, 5 seeds each):

- 30 three-generation families: each grandparent has 2 children, each child has 2
  children. All 180 "is parent of" facts are given.
- For 20 of the families, every "is grandparent of" fact is given as an example (80).
- For the other 10 families, **no** grandparent fact is given (40 per run).

The engine's own output, seed 0:

```
ACCEPT [? is parent of ?](a,b) & [? is parent of ?](b,c) => [? is grandparent of ?](a,c)
       n=120 k=80 rate=0.67 lift=13.3 | where answer known: 80, agree=1.00 | tier=tendency
```

It found the rule "a parent's parent is a grandparent". In the 80 chains where the answer
was known, it agreed every time. Across 5 runs it then inferred **all 200 grandparent links
for the families it had never seen a grandparent example for, with 0 wrong**.

### 6.2 Example quality decides what is learned

The same task, varying the teaching examples. Rows are means over 5 seeds; "shown" is the
share of grandparent facts given as examples, the rest are hidden and scored.

| Families | Shown | Wrong examples | Rule learned | Hidden facts inferred | Wrong inferences |
|---|---|---|---|---|---|
| 6 | 50% | 0% | 0 of 5 runs | 0% | 0 |
| 6 | 75% | 0% | 0 of 5 runs | 0% | 0 |
| 30 | 25% | 0% | 0 of 5 runs | 0% | 0 |
| 30 | 50% | 0% | 5 of 5 runs | 100% | 0 |
| 30 | 75% | 0% | 5 of 5 runs | 100% | 0 |
| 30 | 50% | 20% | 5 of 5 runs | 100% | 0 |
| 30 | 50% | 40% | 0 of 5 runs | 0% | 0 |

Read the table as a programming manual:

- **Too few cases teaches nothing.** With 6 families, grandparent links are common among
  all possible pairs, so the rule cannot rise far enough above chance (lift 2.5 against a
  bar of 5) however complete the examples are. Breadth is what makes a pattern
  distinguishable from coincidence.
- **Too sparse teaches nothing.** With only 25% of conclusions shown, the rule holds in too
  few visible chains to pass.
- **Enough, complete-enough examples teach the rule perfectly**, and it transfers to
  everything not shown.
- **Some bad examples are tolerated** (20% wrong: still learned, still 0 wrong inferences).
- **Too many bad examples are refused, not learned** (40% wrong: no rule, 0 wrong
  inferences). The evidence test fails safe: unclear teaching produces silence, not
  confident nonsense.

In every row, wrong inferences stayed at 0. Example quality moved the system between
"learned it" and "declined to learn it", never into "learned it wrong".

### 6.3 How to write good examples

1. **Show premises and conclusions together, for the same entities.** A rule is scored on
   chains whose conclusion is stated (k). Conclusions about people whose parents are not
   given teach nothing.
2. **Teach some cases completely rather than all cases partially.** The strongest design
   above gave complete examples for 20 families and none for 10. Complete cases let the
   engine judge the rule where the answer is known (agreement 1.00), which is the most
   reliable evidence it has.
3. **Cover enough distinct cases.** At least 3 confirming chains is the hard minimum, but
   in practice the cases must be numerous and varied enough that the conclusion is rare
   among all possible pairs (lift ≥ 5). Dozens of cases, not a handful.
4. **Keep examples consistent.** Mistakes are tolerated up to a point; past it the rule is
   refused.
5. **Stay within the expressible shapes.** Examples can teach inverses, symmetries and
   two-step compositions. They cannot teach a condition ("only farmers harvest") or a
   three-premise rule; examples of those will be learned as an over-general rule or not at
   all (section 7).
6. **Unteach with `RETRACT`.** Removing the examples removes their evidence exactly, and
   the rule goes with it.

### 6.4 What the label tells you

The grandparent rule was learned perfectly but labelled a **tendency**, not a law. That is
correct behavior, not a defect. The engine saw 120 chains but only 80 stated conclusions,
and it cannot tell whether the other 40 grandparents are missing or false (section 2.6).
Its reliability estimate (0.67) reflects that uncertainty about the *data*, not a doubt
about the 80 cases it checked.

How to give the engine grounds to call a taught rule a law is an open question we have not
yet tested. Candidates include complete examples paired with an inverse relation (which
lets it estimate coverage) and explicit negative examples.

### 6.5 How far can it go? Mathematics by example

Can examples program something harder than family trees? Two tests from arithmetic, scripts
in `examples/programming_by_example/`, 5 seeds each.

**Divisibility.** The numbers 2 to 150 and every true fact "a divides b". Half are given; the
other half (241 per run) are hidden. Nothing says that divisibility is transitive.

```
ACCEPT [? divides ?](a,b) & [? divides ?](b,c) => [? divides ?](a,c)
```

The engine learned transitivity in 5 of 5 runs and inferred **319 of 319 hidden facts that
logically follow from the given ones, with 0 wrong**. The other hidden facts, such as "3
divides 6", have no intermediate number to chain through, so they cannot be deduced from
the evidence, and the engine did not produce them. It recovered exactly what follows,
nothing more.

**Remainders modulo 3.** The numbers 0 to 89, with "a is three more than b" for every pair,
plus a decoy that is true but useless here, "a is one more than b". The remainder mod 3 is
given for a random half of the numbers.

```
ACCEPT [? is three more than ?](a,b) & [? has remainder ?](b,c) => [? has remainder ?](a,c)
       ... tier=law
```

It chose the right relation and ignored the decoy, and rated the rule a law: remainder has
one value per number, and the rule agreed 100% where the answer was known. For the
numbers it was never told about:

| Unseen numbers (5 runs, 225 total) | Count | Computed correctly |
|---|---|---|
| A taught number within 4 steps below | 192 | **192**, 0 wrong |
| No taught number anywhere below | 17 | 0: not determinable from the evidence |
| A taught number, but more than 4 steps below | 16 | 0: beyond the engine's 4 inference rounds |

**What this shows, precisely.** Example-programmed logic can be as deep as the evidence
supports, within three bounds:

1. **The evidence.** It derives what logically follows from the facts, and nothing else.
   Missing premises mean missing conclusions, never invented ones.
2. **The rule shapes.** Reasoning must be expressible as chains of two-place relations:
   ordering, divisibility, equivalence, membership, ancestry, containment. It cannot
   represent a three-place fact such as "a plus b is c", so it cannot learn addition
   itself, only relations defined over results.
3. **The depth.** Inference runs for at most 4 rounds, so very long chains are cut off. This
   is a parameter in the code, not a limit of the method.

So the honest form of the claim is not "inference can be as complicated as you want". It is:
**any reasoning that decomposes into chains of simple relations can be programmed with
examples, and it will be exactly as complete as the evidence you provide.** Widening the
second bound (richer rule shapes) is how the architecture would reach further into
mathematics.

### 6.6 Why this matters

| | Written rules | Trained model | Examples in EGM |
|---|---|---|---|
| How logic is specified | Code | Large labelled datasets and training runs | Dozens of example facts |
| Inspectable | Yes | No | Yes: the rule, its evidence and every proof |
| Changing it | Edit and redeploy | Retrain | Add or retract facts |
| Wrong or unclear input | Wrong behavior | Silent errors | Rule refused, or labelled a tendency |
| Needs a programmer | Yes | Yes | No: a domain expert can write examples |

The idea has a long history under the names *programming by example* and *inductive logic
programming* (see references). What is distinctive here is the combination: every taught
rule is accepted or refused by an explicit evidence test, labelled with its reliability, and
leaves a proof on every fact it produces.

The same property cuts both ways, which is the honest limit of the idea: **the logic is
only as good as the examples.** Consistent, coincidental patterns in the examples teach
coincidental rules (the decoy failures in section 5). Teaching by example moves the
responsibility for correctness from code into data, so the data deserves the same care
code does.

---

## 7. Information limits: what no version can do

Some failures are bugs. These are not: they are limits of the information in the data, and
no engineering removes them. Recognizing them prevents wasted work and dishonest fixes.

1. **Missing is not false.** Without negative facts, "not stated" and "untrue" look
   identical. Every rate is measured against what is stated, so hidden data makes true
   laws look weaker (transitivity at 46% in section 4).
2. **Identical evidence cannot be told apart.** A law stated 30% of the time and a rule
   true for 60% of people produced the same signal (0.86 vs 0.84; *Improvement
   Experiments*). No threshold separates them; only new kinds of information can: negative
   facts, conditions, more coverage.
3. **Strong correlation looks like law.** Counts cannot tell causation from coincidence.
   The honest response is a label, not a guess.
4. **One observation cannot generalize.** A name seen once cannot form a category and so
   cannot fill a slot (the cold-start limit). An entity with no facts cannot be reasoned
   about at all.
5. **Structure-free data does not compress.** Random identifiers, balances and
   coordinates have no regularity to find. No architecture compresses or generalizes them
   below their entropy.
6. **Expressiveness bounds discovery.** The engine finds only patterns of the shapes it can
   express (two-slot relations; inverse, symmetric and two-step rules). A regularity of
   another shape is invisible to it, however strong.
7. **Logic is only as good as its evidence.** Wrong facts in produce confident wrong
   inferences out, labelled by how often the rule held, not by whether the premises were
   true.

**The system does not create logic. It discovers logic already implicit in its evidence,
within the shapes it can express, and tells you how strongly the evidence supports it.**

---

## 8. Design principles for developers

These principles produced every result above and explain every rejected idea.

1. **Find the layer that owns the problem.** Change over time looked like an inference
   problem; it was an evidence problem. Fixing it in layer 5 left inference untouched, and that
   design was the one recommended.
2. **Fix the cause, not the case.** A fix must be tested on every world, not just the one
   that motivated it. Three rejected variants each fixed one world and broke another: a
   representativeness check (company world locations 318 → 16), a two-sided coverage
   threshold (containment world 90 → 0), and law-only contradictions (detection 17 of 20 → 0
   under noise). The adopted coverage fix helped its target and changed nothing elsewhere.
3. **Do not compensate for missing information in code.** If the data cannot distinguish
   two situations (section 7), add information or a label. Do not tune a threshold until
   one dataset passes.
4. **Keep new behavior switchable.** Every behavior beyond the v2.0 core can be turned off
   (`SET COVERAGE`, `LABELS`, `CORROBORATE`, `STALE`, `OBS`, `DX`, `REFRESH` …), and with
   them off the engine must reproduce the previous version byte for byte.
5. **Never discard the evidence trail.** Proofs, sources, history and labels are the
   product, not debugging output. Any optimization that loses them is a regression.
6. **Prefer one general mechanism to many special ones.** All the behaviors in section 5
   come from count → test against evidence → apply with proof. A feature that needs new,
   separate machinery probably belongs in another layer, or reflects a mechanism not yet
   understood.
7. **The engine is general; precision is the user's.** The core must not be reduced to
   one use case anywhere in its chain. It represents and discovers associations and relations
   of any kind, from any vocabulary. It contains no domain words: the only English words in
   the engine belong to an experimental, off-by-default amendment study. Which inferences to
   trust, how far to chain them, and how the data is designed are the user's decisions. The
   engine supports them by exposing evidence, tiers (`law`, `tendency`), proofs (`ASK`,
   `CHAINS`) and limits (`[LIMIT]`), and by offering opt-in controls (`TENDENCYSTEPS`, `VOTE`,
   `QUARANTINE`, …), each documented with its measured cost and gain (`docs/SETTINGS.md`).
   A control that helped one dataset is still not a default (`studies/noise`,
   `studies/tendency`).
8. **Do not solve in the engine what needs more data.** When the data cannot decide
   (correlation versus law, which of three equal reports is right, whether a noisy fact is
   wrong), the honest output is a label, a conflict or "unknown". Guessing harder makes the
   engine opinionated about data it cannot judge. More information comes from the user:
   verified facts, better-designed data, or a pipeline that knows which relations are
   one-value.
9. **Correct upstream, rebuild cheaply.** Filtering, deduplication and verification belong
   in the data pipeline, where the developer knows the sources. Redundant reports can be
   reduced there, as long as ties become "unknown" rather than "all of them"
   (`studies/tendency`, X2). To undo a bad change, fix the facts and rebuild, or restore the
   last good knowledge base. At 19,000 facts a full rebuild took under a second, and
   `LOAD` plus a first query 1.4 seconds. The engine does not need in-place repair
   machinery.
10. **Capacity limits are reported, never silent.** Every cap is a setting (`MAXWORDS`,
    `MAXRELATIONS`, `DEPTH`, …), and hitting one prints a `[LIMIT]` line that names the
    setting.

---

## 9. Glossary

- **Record**: one ingested line, stored exactly; identical lines share a record.
- **Open word**: a word in a category of at least two; it can fill a relation slot.
- **Relation (template)**: a sentence shape with two slots, e.g. `? lives in ?`.
- **Chain (n)**: an instance where a rule's premises hold.
- **k**: chains whose conclusion is also stated.
- **Rate**: k / n. **Base rate**: how often a random pair satisfies the conclusion relation.
- **Lift**: rate / base rate.
- **PCA agreement**: rate counted only where the subject's answer is known.
- **Coverage**: estimated completeness of a relation's data, from strong inverse rules.
- **Reliability**: estimated probability that a rule's conclusions are true.
- **Law / tendency**: reliability ≥ 0.95 / below.
- **One-value (functional) relation**: at least 95% of subjects have exactly one object.
- **Fixpoint**: the state where applying the rules again derives nothing new.
- **Projection**: computing what holds now from the observation log.
- **Snapshot / partial**: an observation stating everything a record says now / adding to it.
- **Stale**: a derived conclusion whose premise has since changed.

---

## 10. References

**Papers in this repository** (`docs/papers/`):

- *Voltex Research & Architectural Assessment*: the v1 audit, the v2 design, categories,
  generation, the containment world.
- *Voltex Blind World Discovery Results*: rule discovery, undesigned rules, multi-hop
  recall, decoys and limits in a hidden world.
- *Voltex Improvement Experiments: Findings and Decisions*: coverage awareness, labels,
  corroboration, retraction, staleness; adopted and rejected variants.
- *Evidential Grammar Memory: A Rule-Discovering, Self-Correcting Memory Tool for
  Language-Model Agents*: EGM with LLM agents.
- *Amendments in Voltex*, *Declarative Amendments in Voltex*, *Dynamic Relational Evolution
  in Voltex*: where change should live.
- *Evidence Before Inference*: source-aware observations (v2.2) and LLM vs EGM.
- *Extract Once, Query Forever*: LLM-extracted facts from a real codebase.
- *Tokenomics of Programmatic Distillation*: cost as the knowledge base grows.

**Prior work the architecture builds on:**

- Nevill-Manning & Witten (1997), *Identifying hierarchical structure in sequences*
  (Sequitur).
- Rissanen (1978); Grünwald (2007), *The Minimum Description Length Principle*.
- Harris (1954), *Distributional structure*; Brown et al. (1992), *Class-based n-gram
  models of natural language*.
- Witten & Bell (1991), *The zero-frequency problem*.
- Galárraga et al. (2013), *AMIE: association rule mining under incomplete evidence in
  ontological knowledge bases* (partial completeness).
- Stolcke & Omohundro (1994), *Inducing probabilistic grammars by Bayesian model merging*.
- Muggleton (1991), *Inductive logic programming*.
- Lieberman (ed.) (2001), *Your Wish Is My Command: Programming by Example*.
- Gulwani (2011), *Automating string processing in spreadsheets using input-output
  examples* (FlashFill).
