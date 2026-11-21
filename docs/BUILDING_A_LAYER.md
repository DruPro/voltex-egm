# Building an analysis layer on Voltex EGM

A **layer** turns some source (a codebase, a table, a log) into facts, gives them to the engine, and reads back what
the engine learned and inferred. The engine stays unchanged; the layer owns extraction, settings and scoring.

This guide is distilled from `studies/stress`. In that study, layers for four code corpora, four real system tables
and synthetic shapes were run through 295 test runs. Every number below comes from there. The report with charts and
proof trees is `studies/stress/report/index.html`.

## 1. The shape of a layer

```
source ──extract──▶ facts.txt ──engine──▶ rules + inferred facts + proofs ──score──▶ findings
                       │                                                     ▲
                       └──── hold out 20% as the answer key ─────────────────┘
```

A minimal layer, for a CSV of employees:

```python
import csv, random, egm

def tok(s):                                   # one token per name: letters, digits, _
    return "".join(c if c.isalnum() else "_" for c in s.strip()).strip("_")

facts = []
for row in csv.DictReader(open("staff.csv")):
    p = tok("p_" + row["name"])
    facts.append(f"{p} works in {tok('dept_' + row['dept'])}")
    facts.append(f"{p} reports to {tok('p_' + row['manager'])}")
    facts.append(f"{p} is based in {tok('city_' + row['city'])}")

r = random.Random(11)                         # hidden key: never given to the engine
stated, key = [], set()
for f in facts: (key.add(f) if r.random() < 0.2 else stated.append(f))
open("facts.txt", "w").write("\n".join(stated) + "\n")

with egm.open("facts.txt") as e:
    for rule in e.rules():
        print(rule.tier, rule.text, f"agree {rule.agree} on {rule.known} known of {rule.n}")
    new = [f for f in e.infer_all() if f.fact not in set(stated)]
    hit = [f for f in new if f.fact in key]
    print(f"{len(new)} derived, {len(hit)} recovered from the hidden key")
    for f in e.ask("p_Ana_Lopez is based in ?"):   # one answer with its proof
        print(f.fact, f.tier, f.because, f.rule)
```

For Python source there is a built-in extractor: `egm extract python NAME=DIR ... -o facts`. It resolves calls across
modules through imports and drops ambiguous names.

## 2. Designing the facts

- **Names are single tokens.** Qualify them so that equal names mean equal things: `numpy__core__shape_base`,
  `pkg_libc6`, `u00E9`.
- **Prefix values by kind** (`dept_`, `cat_Lu`, `prio_optional`). The engine groups words that share contexts into
  categories, and a prefix keeps a city from looking like a person.
- **One relation per fact, as a verb phrase:** `calls`, `is defined in`, `depends on`. Use the same phrase every time.
- **Give every fact an object.** `x is mirrored` has none; write `x has property mirrored`.
- **Know what your extractor guarantees.** Two "discoveries" in the study were artifacts of extraction:
  - an extractor that records only same-module calls makes "callers live in the callee's module" true by
    construction;
  - one that records fields only for structs makes "has a field ⇒ is a struct" true by construction.

  Before you report a learned rule as a finding, ask whether your extractor made it true.

## 3. Hold out a key, and know what it misses

Hide a seeded 20% of the facts and score what the engine derives against them:

- **recovered** = derived facts in the key;
- **precision** = recovered / derived;
- **recall** = recovered / key.

The key undercounts precision whenever true facts can lie outside it:

| Data | Precision against the key | Against full truth |
|---|---|---|
| Unicode (characters outside the extracted range were reached through case partners) | 0.83 | 0.962 (`unicodedata`) |
| dpkg, `DEPTH 1` (indirect dependencies are true but not in a direct-only key) | 0.080 | 0.876 (transitive closure) |

Where you can compute truth directly, do it (`studies/stress/tools/verify.py` shows both cases).

## 4. Settings are per dataset

There is no single best setting; choose with evidence from your own data. What the study measured:

| Setting | Helps when | Hurts when | Measured |
|---|---|---|---|
| `TENDENCYSTEPS 0` (law-tier proofs only) | a weak rule floods the answers | the true rules are tendencies | Python packages: precision 0.010 → 0.963, same recall. Company data: recall 0.956 → 0.491 |
| `DEPTH 1` / `2` (fewer inference rounds) | rules chain widely (dependency graphs) | answers need long chains (family trees) | dpkg: 13,000 facts at 88% true with `DEPTH 1`, against 1.15M at 4% with the default 4 |
| `DEPTH 0` (until nothing new) | closures are small | anything chains widely | dpkg: out of memory after 340 s |
| `COVERAGE 0` | data is sparse, like code | dense data | real Python code: the default passed 18 GB; with `COVERAGE 0` it ran in 148 MB |
| `MAXWORDS` = vocabulary + 1,000 | the vocabulary exceeds 12,000 words (the `[LIMIT]` line says so) | rarely | needed for 8 of 31 datasets |
| `TREES 1`, `CHAIN 3` | gates, family trees | coincidence-rich data | see `docs/SETTINGS.md` |

A quick procedure for a new dataset:

1. Run it with defaults. Look for `[LIMIT]` lines with `e.limits()` and fix `MAXWORDS` first.
2. Read `e.rules()` (section 5).
3. Count `e.chains()` by round and tendency steps. If most answers come from one round past the first, or from one
   rule, try a lower `DEPTH` or `TENDENCYSTEPS 0`, and score each against the key.
4. Use `ask(..., strict=True)` where a wrong answer costs more than a missing one.

## 5. Reading the learned rules

Each rule reports:
- `n`: chains that matched its premises;
- `k`: chains whose conclusion was also stated;
- `rate` = k / n;
- `lift` over the base rate;
- `agree` on `known` cases where the answer was known;
- `tier`: law or tendency.

Signs of a rule to distrust:
- **Huge `n`, tiny `known`.** "A function inherits its module's imports" agreed on 80 of 98,782 cases and produced
  100,859 of 108,323 derived facts.
- **Low agreement at law tier.** In dpkg, `a recommends b ⇒ b depends on a` agreed on 15% of known cases and was
  labelled law. It reverses the direction, and transitivity grows its errors about 4× per round.
- **Lift near or below 1.** The rule predicts the base rate, nothing more.

Signs of a real regularity: high agreement on many known cases, at both tiers. Examples from the study:
- Unicode case pairs are inverses (0.98 on 589 cases).
- Accented letters inherit their base letter's category (0.96 on 477).
- In real code, callers live in the callee's module (0.82 on 10,372).

## 6. Showing the reasoning

`ask()` returns each inferred fact with `because` (its premises) and `rule`. To build a full proof tree, ask again for
each premise that is itself inferred (`studies/stress/tools/explore.py`, `proof()`):

```
numpy _block_slicing is defined in numpy._core.shape_base        [tendency]
├── _block_slicing calls _block_info_recursion                   (stated)
└── _block_info_recursion is defined in shape_base               [tendency]
    ├── _block_info_recursion calls atleast_nd                   (stated)
    └── atleast_nd is defined in shape_base                      (stated)
```

The engine's mistakes are often the most informative output. Most of its 50 wrong Unicode facts fall on Unicode's
documented exceptions, such as titlecase Greek letters with iota subscript and one-way case pairs like the Kelvin sign.

## 7. Cost: where the time goes

- **Ingest is fast:** 81,000 to 122,000 facts in 0.35 to 0.63 s.
- **The model build is usually seconds.** Categories dominate with large vocabularies.
- **Inference is the cost when rules chain widely.** dpkg: the model built in 0.1 s, but `INFER ALL` took 59 s and
  3.1 GB, deriving 1.15 million facts from 14,296.
- **Updates rebuild from scratch** when the new facts bring new names: 1.0 to 1.5× a full build in every dataset.

Prefer `ask` for single questions; `infer_all` computes everything.

## 8. Testing changes the same way

`studies/stress/tools/bench.py` runs any engine binary over every dataset × setting × script cell and compares output
hashes:

```
python3 studies/stress/tools/bench.py catalog                 # build datasets (into studies/stress/obs, git-ignored)
python3 studies/stress/tools/bench.py run BIN runs/new.jsonl  # one fresh process per cell, /usr/bin/time, 12 GB cap
python3 studies/stress/tools/bench.py compare runs/a.jsonl runs/b.jsonl
```

Pitfalls found while building it:
- **Mask paths before comparing output.** `LOAD` prints the knowledge base's path, which differs per run.
- **Measure memory with `/usr/bin/time`** from a small shell. A Python harness's own `wait4` reading includes the
  parent's high-water mark.
- **Keep machine paths out of results files.** Record binary names, not full paths.
- **Build datasets on the machine that runs them.** The corpora depend on what is installed (`manifest.json` records
  each dataset's sha256).
