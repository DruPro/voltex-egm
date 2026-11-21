# Designing data for deliberate inference

The engine learns rules from the facts you give it and applies them with proofs. That means you can
*program* what it infers by deciding what facts to write and how to write them. This guide is about
designing data for a specific outcome: a lookup that follows a chain, a decision table, a computation
in layers, a rule that holds only for one group. It also covers composing several engines into a larger
system.

The engine stays general and leaves precision to you. It finds any association your data supports, and you
decide, by designing the data and choosing settings, which ones it should find and how far to trust them.

Why design data instead of training a model:
- What it learned is a short list of readable rules, each with its evidence.
- Every answer comes with its proof.
- Changing behavior means changing facts and rebuilding, which takes about a second at 19,000 facts.
- Nothing is learned that the data does not support: the random control in 2.4 accepted no rules.

Every example below was run on the engine in this repository. The output lines are quoted from those runs,
shortened only where marked `…`. `python3 examples/data_design/verify_examples.py` reruns them all and checks
each number quoted here (16 checks).

---

## 1. How the engine reads your facts

| Rule | What it means for your data | Verified |
|---|---|---|
| One line is one fact. | `emp07 works at acme03` | |
| An entity is one word. | Write `new_york`, not `new york`. With `new york`, 18 of the 70 city facts and 2 of the 8 office facts dropped out of their relations, and the chain answer for New York employees disappeared. With `new_york` all were kept and the answer was inferred. | §1.1 |
| A relation is the words around two entities, written the same way every time. | Pick one phrase per relation (`works at`) and never vary it (`is employed at`, `works for`). | |
| A relation phrase must not look like an entity. | Words that appear in the same position as other words are grouped into categories, and a grouped word can be read as an entity. `acme00 is located in oslo` next to `emp00 is based in oslo` made *located* look like *based*: the engine read `? is ? in oslo` and learned no rule. `acme00 has headquarters in oslo` worked. | §1.1 |
| It learns only from what is stated. | There are no negative facts: something not stated is unknown, not false. | |
| A rule needs evidence. | At least 3 confirming cases (`SUPPORT`), and it must beat the base rate clearly. | |

### 1.1 The office example (two relation phrasings)

```
emp00 works at acme00          acme00 has headquarters in oslo
emp00 is based in oslo         … 80 employees, 8 companies, city stated for 70 employees
```

```
ACCEPT [? works at ?](a,b) & [? has headquarters in ?](b,c) => [? is based in ?](a,c)  n=80 k=70 … agree=1.00 … tier=law
emp75 is based in kyiv   inferred [law] (score 1.00) because emp75 works at acme03 + acme03 has headquarters in kyiv
```

With `acme00 is located in oslo` instead, the relation list showed `? is ? in oslo` (2 facts) and no rule was
accepted. Run `RELATIONS` first and check that every relation you meant appears, exactly once.

---

## 2. The rule shapes, and the facts that teach each

| Shape | Write facts like | Setting | Example below |
|---|---|---|---|
| Inverse | `box05 contains item45` and `item45 is in box05` | default | 2.1 |
| Two-step chain | `x works at c`, `c has headquarters in y`, `x is based in y` | default | 1.1 |
| Longer path (3 to 8 steps) | `a is parent of b` … `a is great grandparent of d` | `SET CHAIN 3` | 2.2 |
| Rule for a group only | the chain facts plus `x works as farmer` | `SET CONDITIONS 1` | 2.3 |
| Tree (several facts about one entity decide) | `o was placed by c`, `c has tier gold`, `c lives in region north`, `o ships express` | `SET TREES 1` | 2.4 |
| Computation in layers | trees whose outputs feed other trees | `SET TREES 1`, `SET DEPTH 0` | `studies/trees` (4-bit adders, 1,700 of 1,700 wires) |

### 2.1 Inverse, and how completeness decides law or tendency

60 items, each `item is in box`. For 40 of them, `box contains item` is stated too:

```
ACCEPT [? contains ?](a,b) => [? is in ?](b,a)   n=40 k=40 rate=1.00 … tier=law
ACCEPT [? is in ?](a,b) => [? contains ?](b,a)   n=60 k=40 rate=0.67 … tier=tendency
```

The second rule is true, but the data stated it for only 40 of 60 items, so the engine could only verify 67%.
With `contains` stated for 57 of 60:

```
ACCEPT [? is in ?](a,b) => [? contains ?](b,a)   n=60 k=57 rate=0.95 … tier=law
box07 contains item57   inferred [law] (score 0.95) because item57 is in box07
```

### 2.2 Longer path

Parent facts for 30 four-generation families; great-grandparent stated for 20 of them:

```
SET CHAIN 3
ACCEPT [? is parent of ?](a,b) & [? is parent of ?](b,c) & [? is parent of ?](c,d) => [? is great grandparent of ?](a,d) n=240 k=160 … agree=1.00
```

All 80 unstated great-grandparents were inferred, with 0 wrong. With the default `CHAIN 2`, none were.

### 2.3 Rule for a group

People live in towns that produce goods, but only farmers and miners harvest them (`tests/worlds.harvest`):

```
default:          ACCEPT … lives in … produces … => [? harvests ?](a,c)                                  rate=0.23 … tier=tendency
SET CONDITIONS 1: ACCEPT … lives in … produces … => [? harvests ?](a,c) if [? works as ?](a,miner|farmer) rate=0.90
```

The general rule would have fired for everyone. Its condition makes it fire only for the group where it holds.
To teach a condition, state the group attribute (`works as`) for everyone, and include enough people outside the
group that the contrast is visible.

### 2.4 Tree: a decision table from examples

400 orders from 60 customers. An order ships express exactly when its customer is gold tier *and* in the north
region. The shipping method is stated for about two thirds of the orders.

```
cust07 has tier gold          (the format; names and values are generated)
cust07 lives in region north
order123 was placed by cust07
order123 ships express
```

```
SET TREES 1
ACCEPT TREE [? was placed by ?](a,g) & [? has tier ?](g,gold) & [? lives in region ?](g,north) => [? ships ?](a,express) … agree=1.00 … tier=law
ACCEPT TREE [? was placed by ?](a,g) & [? lives in region ?](g,south) => [? ships ?](a,standard) … agree=1.00 … tier=law
ACCEPT TREE [? was placed by ?](a,g) & [? has tier ?](g,basic) => [? ships ?](a,standard) … agree=1.00 … tier=law
```

All 133 hidden orders were inferred, with 0 wrong. The three rules above are the smallest complete table: express
needs both conditions; either one failing is enough for standard. Without `TREES` it inferred nothing.

It also accepted a fourth tree rule, the reverse:

```
ACCEPT TREE [? was placed by ?](g,a) & [? ships ?](g,express) => [? has tier ?](a,gold) n=11 k=11 … tier=law
```

"A customer with an express order is gold" is true in this data, so it would fill in a missing tier. Read every
accepted rule, not only the ones you designed for.

**Control.** The same data with shipping chosen at random, plus a random `likes color` attribute: 0 rules accepted,
0 facts derived. A pattern that isn't in the data is not invented.

**Designing a tree:**
- State every attribute that decides the outcome, as a short value word (`gold`, `north`, `zero`, `one`).
- Include examples of every outcome and every combination that matters. The engine has no negative facts, so the
  contrast has to be there in the examples.
- The outcome relation should have few values: up to 8.

---

## 3. Leave whole entities unanswered, not half-answered

This is the most useful single rule for getting `law` answers. The engine judges a rule where the answer is known:

- **Partly answered.** In 2.1 every box had some `contains` facts, so the 20 missing ones counted as failures: 67%,
  tendency.
- **Wholly unanswered.** In 1.1, ten employees had no city stated at all. They didn't count against the rule, and
  where the city was known the rule agreed 100%, so it was law even though only 70 of 80 cities were stated.

So: **teach with complete examples, and leave the cases you want inferred completely empty.** Don't scatter gaps
through every entity.

Where you can't do that, the answer is labelled `tendency`, which is honest. You decide how to use it: read the
labels, or set `TENDENCYSTEPS 0` to keep only law-tier answers. That setting is measured in `docs/SETTINGS.md`.

---

## 4. Decide what may follow from what

| You want | Do | Measured in |
|---|---|---|
| Only answers whose whole proof uses law-tier rules | `SET TENDENCYSTEPS 0`, or `strict=True` in the SDK | `studies/tendency` (precision 0.97-1.00) |
| Multi-step computation to finish | `SET DEPTH 0` (run until nothing new) | `studies/depth`, adders |
| To see how answers were reached | `CHAINS` (round and tendency steps per fact), `ASK` (proof) | `studies/tendency` |
| To check you hit no limits | `RELATIONS` prints `[LIMIT]` lines; raise `MAXWORDS` / `MAXRELATIONS` | `studies/tendency` T5 |

---

## 5. Several engines working together

One engine has one set of settings and one vocabulary. When parts of a problem need different settings, or you
want a deliberate gate between parts, use several engines and pass facts between them.

### 5.1 Verified example: two stages

- **Stage A** (`TREES 1`) learns the shipping table from 2.4.
- Only its **law-tier** conclusions are passed on.
- **Stage B** (default settings) learns which carrier takes each order: `express is handled by fastco`, and so on,
  plus 150 orders whose carrier is stated.

```python
import egm
with egm.open("A.txt", settings={"TREES": 1}) as a:
    law = [f.fact for f in a.infer_all() if f.tier == "law"]       # the gate: only law-tier facts cross
with open("B.txt", "w") as out:
    out.write("\n".join(shipping_facts + law + carrier_facts) + "\n")
with egm.open("B.txt") as b:
    carriers = {f.subject: f.object for f in b.infer_all() if f.relation == "goes with"}
```

Measured:
- Stage A derived 133 law-tier facts and 0 tendency facts.
- Stage B learned `[? ships ?](a,b) & [? is handled by ?](b,c) => [? goes with ?](a,c)` and got 250 of 250
  untaught orders right, with 0 wrong.
- A single engine given all the facts with `TREES 1` also got 250 of 250. So here staging adds **control, not
  capability**.

### 5.2 Why stage at all

| Reason | Evidence |
|---|---|
| **Different settings per part.** One engine must pick one value per setting. | Measured: `CHAIN 3` was right for family trees (0 to 1.0 F0.5) but cut another world from 0.775 to 0.636 (`studies/noise`, cross-world transfer). |
| **A gate between parts.** Pass only law-tier facts, or only facts you have checked. | The pattern of 5.1. It is the architecture-level version of `TENDENCYSTEPS 0`. |
| **Separate vocabularies.** Each engine stays under its capacity caps, and unrelated domains can't form coincidence rules with each other. | Caps: measured (`studies/tendency` T5). Coincidences across domains: a design argument, not measured here. |
| **Rebuild one part alone.** | Rebuilds take about a second per 19,000 facts (`studies/tendency` T6). |

### 5.3 Sharding: when one engine gets too big (measured)

One engine's memory grows faster than its facts. In the company world it took 2.1 GB at 122,042 facts and 8.4 GB at
244,444. The cause is word-category building, which is quadratic in vocabulary (`studies/scaling`). You can split the facts over several unchanged engines and take the union of their answers. This gave
answers **identical** to one engine (`studies/shard`), but only with the right split.

1. **Split on a relation you know is clean.** Put each connected component of that relation's graph in one shard,
   and attach any entity whose links all point into one shard.
   - Don't split on a relation the noise can corrupt. Splitting people by their stated team put people with a wrong
     team in the wrong shard: precision 1.000 fell to 0.876 at 15% noise.
   - Splitting by `collaborates with`, which the noise never touched, kept 1.000.
2. **Send shared reference facts** (teams, departments, cities) to every shard that mentions them, following them
   from subject to object.
3. **Keep only answers whose rule most shards accepted.** Each shard decides about borderline rules on less
   evidence, and a union keeps any shard's yes. This needs each answer's proof (one `ASK` per derived subject and
   relation), so it costs a second pass per shard, but stays at or below one engine's CPU. In a pre-registered test
   (15% noise, fresh seeds), it made the answers identical to one engine in 9 of 9 runs, and changed nothing on clean
   data. Whether it is needed is a matter of chance: without it, 16 shards had 40-241 wrong answers and 8 small
   shards 38-83, but 8 shards of 160 teams had none on those seeds (and some on others). Use it whenever the data
   may be noisy.
4. **Optional:** learn the reference rules once, centrally, and pass the law-tier conclusions to the shards
   (the two-stage gate of 5.1). It changed nothing at 160 teams per shard, because each shard could learn the rules
   itself. It may matter when shards are small.

Measured with 16 shards at 244,444 facts: 22.7 s CPU and 254 MB per engine, against one engine's 47.3 s and 8,350 MB.
The answers were the same. The layer is `studies/shard/tools/shard.py`; it uses the engine only through its CLI.

This was shown on one world shape. It depends on knowing which relation noise can't touch; that is a property of your
sources, which the engine can't judge for you.

### 5.4 Other patterns (design ideas, not yet measured)

- **Specialists and a router.** One engine per domain; your code sends each question to the one that owns that
  relation.
- **Agreement.** Run the same question through engines built from independent sources, and accept an answer only
  if they agree. This is the pipeline-level version of `VOTE`.
- **Feedback with review.** A stage's tendency-tier answers go to a person or a test. Only confirmed ones are added
  as facts for the next build.

---

## 6. Check a design before relying on it

1. `RELATIONS`: is every relation you meant there, once, with the right phrase? Any `[LIMIT]` lines?
2. Rules (`egm rules KB`): is each intended rule accepted, with the tier you expected? Read `n`, `k` and `agree`.
3. Hold back answers you know, and check the engine infers them. `egm tune facts.txt` does this automatically for
   settings. A small hidden test set of your own is better.
4. `CHAINS` and `ASK`: do the proofs look the way you designed them?
5. `CONFLICTS`: on data you believe is correct, every conflict is either a data error or an exception worth knowing
   about.

---

## 7. Anti-patterns

| Don't | Because | Instead |
|---|---|---|
| Write multi-word names | They split into several words and break relations | `new_york`, `acme_corp` |
| Vary the phrase of one relation | Each phrasing becomes a separate relation | One phrase per relation |
| Reuse one frame for different relations (`is located in`, `is based in`) | The relation words can be read as entities | Distinct phrases (`has headquarters in`) |
| Leave gaps in every entity | Rules look like tendencies | Complete teaching examples; wholly empty question cases |
| Expect it to learn from what isn't there | Missing is unknown, not false | State contrasts explicitly (both outcomes, both groups) |
| Feed unreviewed outputs back as facts | Errors become evidence | Gate on law tier, or review first |
| Fix mistakes inside the engine | It has no repair logic, by design | Fix the facts, rebuild or restore a backup (about a second) |
