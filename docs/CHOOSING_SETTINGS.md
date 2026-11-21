# Choosing settings for what you are trying to do

Voltex EGM has no one-size-fits-all configuration. The same setting that fixes one dataset can halve the answers on
another. This page says which settings to reach for, case by case, when not to, and what each costs. Every number
comes from a measured run. Most are from the 295-run stress bench (`studies/stress`), which covers real code, real
system tables and synthetic shapes, scored against a hidden 20% of each dataset. The rest come from earlier
pre-registered studies, which are linked. For what each setting does, see `docs/SETTINGS.md`.

**Precision** is the share of new answers that are true, and **recall** the share of the hidden facts recovered.
"P / R 0.84 / 0.50" means both.

## Start here: four steps for any new dataset

1. **Size `MAXWORDS` to your vocabulary.** If `e.limits()` (or a `[LIMIT]` line) says the categories cover fewer
   words than you have, set `MAXWORDS` to the number of distinct words plus about 1,000. Below the cap, facts about
   rarer names can't be asked about at all, not even stated ones. Company data, 122,042 facts: recall 0.63 at the
   default cap, 0.957 sized. Since `CLUSTERSTREAM` (on by default), raising it no longer costs quadratic memory.
2. **Run with defaults and read the rules.** `e.rules()` shows each rule's evidence (section "Reading the rules").
3. **Count how answers were reached.** `e.chains()` gives each derived fact's round and number of tendency steps. If
   most answers come from one rule, or pile up in later rounds, the data is chaining widely; see `DEPTH` and
   `TENDENCYSTEPS` below.
4. **Hold out a key and compare settings.** Hide a seeded 20% of your facts and score each candidate setting on it
   (`docs/BUILDING_A_LAYER.md`). Choose by your own numbers, not by this page's. `egm.tune(facts, expanded=True)`
   automates the comparison (`docs/SDK.md`).

## By goal

| You want | Start with | Why (measured) |
|---|---|---|
| Answers you can act on without checking | `ask(..., strict=True)`, and `TENDENCYSTEPS 0` | Only law-tier proofs. Python packages: precision 0.010 → 0.963. Expect lower recall |
| Code facts extracted by a parser (tested on two Python codebases) | try `TENDENCYSTEPS 0`, plus `TREES 1`, `CHAIN 3`, `DEPTH 0` as the questions need, and validate on your data | stdlib: 5,829 of 5,901 hidden facts; Debian packages (1M lines): 17,265 of 17,269 law-tier answers true ([STRENGTHS.md](STRENGTHS.md)) |
| As many leads as possible, to check by hand | defaults, `strict=False` | Tendencies included; each answer carries its proof and tier |
| Analysis of a codebase | `COVERAGE 0`, `MAXWORDS` sized, then compare `TENDENCYSTEPS 0` and `CONDITIONS 1` | Code is sparse; the default ran past 18 GB on 125 packages. Precision with `CONDITIONS 1`: 0.01 → 0.88 |
| Transitive data (dependencies, containment, routes) | `DEPTH 1` or `2`, and compare with `COVERAGE 0` | dpkg: `DEPTH 1` gives 88% true facts; the default `DEPTH 4` gives 4% |
| Several attributes deciding one value (truth tables, configurations, pricing rules) | `TREES 1` | Gates: recall 0 → 0.78 at 1.00 precision |
| Relations three or more hops away (great-grandparents, org depth) | `CHAIN 3` | Lineage: nothing → 1.00 / 1.00 |
| A rule that holds only for one group | `CONDITIONS 1` | Found "only farmers and miners harvest", errors down 98% |
| The same fact reported by several sources, some wrong | `VOTE 1` | 3 reports, 15% wrong each: precision 0.32 → 0.998 |
| Noisy single reports | try `QUARANTINE 1` and score it | Recall 0.72 → 0.93 on noisy company data, but lower precision with `TREES` |
| Frequent small updates | `REFRESH` (experimental) | Reuses categories and rules; inference still reruns in full |
| Huge vocabularies on one machine | `MAXWORDS` sized; `CLUSTERSTREAM` is already on | 244,444 facts in 256 MB |

## Setting by setting

### `MAXWORDS` (default 12,000)

- **Use** whenever your data has more distinct words than the cap. Check `e.limits()`.
- **Don't lower it** to save time: at 300 words, recall fell to 0.00–0.36 on every dataset.
- **Cost:** build time grows with vocabulary. Memory no longer grows quadratically.
- **Watch for this:** at the cap, an empty answer can mean "this name is beyond the cap". A Sonnet session answered
  "not in the knowledge base" for this reason (`docs/AGENT_SESSIONS.md`, session 0). Empty answers from `egm mcp`
  and `explain()` now say "unknown, not false" and name the cap, but the fix is still to size `MAXWORDS`.

### `DEPTH` (default 4 rounds; 0 = until nothing new)

- **Lower it (1-2)** when a relation chains widely: dependencies, imports, "part of", "connected to". On dpkg:

  | `DEPTH` | Derived facts | True |
  |---|---|---|
  | 1 | 13,000 | 87.6% |
  | 2 | 60,537 | 50.9% |
  | 4 | 1,151,048 | 4.2% |

- **Raise it, or use 0,** only when answers really need long proofs and the closure is small: family trees, adders
  built from gates (`studies/depth`).
- **Don't use 0** on graph-like data: dpkg ran out of memory after 340 s. On a precedence chain, `DEPTH 0` took
  precision from 0.19 to 0.05.
- **Cost:** each extra round can multiply the derived set (about 4× per round on dpkg).

### `TENDENCYSTEPS` (default -1 = no limit; 0 = law-tier proofs only)

- **Use 0** when one weak rule floods the answers. Python packages: precision 0.010 → 0.963, with the same recall.
  Hidden world: 0.974 → 0.999.
- **Don't use it** when your true rules are only partly stated, because they then count as tendencies:
  - company data: recall 0.956 → 0.491, and with 15% noise 0.65 → 0.22;
  - precedence chains: every answer lost;
  - real code with call locality: 108,323 facts → 73.
- **It doesn't help** when the bad rule is law tier. dpkg kept 1,150,230 facts.
- **1** barely differs from no limit, because floods are usually one tendency amplified by law rules
  (`studies/tendency`).
- Per question, `ask(..., strict=True)` does the same thing.

### `COVERAGE` (default 1: relax the rate bar when data looks sparse)

- **Use 0** on sparse data: code, package graphs, anything where most possible facts are simply absent.
  - real code: the default ran past 18 GB, while `COVERAGE 0` ran in 148 MB;
  - dpkg: precision 0.00 → 0.78 (662 facts, recall 0.46 → 0.14);
  - hidden world ×8: 0.84 → 0.98.
- **Keep 1** on dense, well-covered data. It changed nothing on company, Unicode or social data.

### `TREES` (default 0, experimental): tree-shaped rules

- **Use** when several facts about one entity decide a value together: a gate's kind and its inputs decide its
  output; a product's tier, region and term decide its price.
  - gates: recall 0 → 0.78 at precision 1.00;
  - noisy company data: recall 0.65 → 0.88;
  - earlier study: 1,319 of 1,332 hidden gate outputs, 0 wrong; 100 of 100 four-bit adders with `DEPTH 0`.
- **Don't use** when nothing combines that way. It changed nothing on code, Unicode or social data, and the mining
  time remains.
- **Cost:** company ×8 took 2 → 35 s, hidden ×8 5 → 51 s, dpkg 97 → 288 s. Under 30% noise, precision 100% →
  97.9% (`studies/trees`).

### `CHAIN` (default 2, experimental; 2-8): rule length

- **Use 3+** for relations that are a fixed number of hops: great-grandparent = parent of parent of parent.
  Lineage: nothing → precision and recall 1.00. Earlier study: 3,000 correct, 0 wrong.
- **Don't use** on coincidence-rich data. Hidden world precision: 0.955 → 0.931 at 3, 0.903 at 4
  (`studies/multipremise`). It changed nothing useful elsewhere in the bench.
- **Cost:** slower mining, about 2-3× on company data.

### `CONDITIONS` (default 0, experimental): rules that hold for one group

- **Use** when a rule is true only for some subjects: "only farmers and miners harvest", "only library functions
  raise".
  - Python packages: precision 0.01 → 0.88, by restricting the module-imports rule to where it held;
  - hidden world: the best precision of any configuration (0.980).
- **Don't use blindly** on small data: one spurious condition came from 9 cases. On the harvest test it cut
  derived facts from 613 to 21.
- **Cost:** small.

### `VOTE` (default 0, experimental)

- **Use** when the same fact arrives several times from independent sources: 3 reports, 15% wrong each, precision
  0.32 → 0.998, recall 0.80 → 0.95.
- **Without repeated reports** it changes nothing. Outvoted facts are listed, never deleted (`studies/noise`).

### `QUARANTINE` and `REPLICATE` (default 0, experimental)

- **`QUARANTINE`** stops counting a stated fact that two distinct rules contradict. Recall 0.72 → 0.93 on noisy
  company data, but with `TREES 1` at 30% noise, precision 0.975 → 0.939. Score it on your data before keeping it.
- **`REPLICATE`** keeps a rule only if it holds in both halves of its subjects. It cut 70% of wrong answers under
  heavy noise, but lost 36% of correct gate outputs on clean data. Not recommended (`studies/noise`).

### `CLASS` (default 0.5)

- In the bench, 0.3 and 0.7 changed nothing on any dataset. Leave it unless categories visibly merge unrelated words
  (`e.categories()`).

### `CLUSTERSTREAM` (default 1)

- Keep it on. It changes no answer and makes large vocabularies cheap. Set it to 0 only to reproduce old timings.

### `REFRESH` (default 0, experimental)

- **Use** for frequent small updates without new names: it reuses categories and rules.
- **Limits:** a new name forces a full rebuild, and inference always reruns in full (`studies/scaling`).

## By data shape (what the bench saw with defaults)

| Data shape | Example | Default outcome | Best measured change |
|---|---|---|---|
| Exact parser output, rules that really hold | Python stdlib and Debian packages (`studies/strengths`) | a flood of tendency-tier facts (precision 0.043 with all settings on) | `TENDENCYSTEPS 0`: precision 0.996, recall 0.988 |
| Dense, consistent relations | company, social | P 1.00, R 0.96-1.00 | none needed |
| Attribute tables with inverse pairs | Unicode | 96% true against the real database | none needed |
| Sparse code facts | Python packages, C headers | P 0.01-0.05 | `CONDITIONS 1` or `TENDENCYSTEPS 0` (P 0.88 / 0.96) |
| Wide transitive graphs | dpkg | 1.15M facts, 4% true | `DEPTH 1` (88% true) or `COVERAGE 0` |
| Truth tables, configurations | gates | nothing derived | `TREES 1` |
| Fixed multi-hop relations | lineage | nothing derived | `CHAIN 3` |
| Random links, independent attributes | zipf, many relations, clusters | nothing derived | correct: there is nothing to learn |
| Values spread over several words | "the north mill 12 is governed from north capital" | nothing derived | write one-token values (`docs/BUILDING_A_LAYER.md`) |
| Very small tables | services, time zones | nothing, or wrong (46 facts, all wrong) | too little evidence; add facts or don't infer |

## What an answer means, and what it doesn't

The engine reports how it knows something. It never says more than that.

| Answer | Means | Doesn't mean |
|---|---|---|
| `stated` | it is in your facts | that your facts are right |
| `law` | a proof whose rules held, with high reliability, wherever the answer was known | that it is true of the real system |
| `tendency` | a proof using at least one weaker rule: a weighted guess | anything you should act on unchecked |
| empty | no stated or inferred answer: **unknown, not false** (the note names any cap) | that the answer is "no" |

- **Law tier is relative to what was observed.** On Debian's Python packages, 4 law-tier answers were false: "this
  method has no decorator". The extractor wrote no decorator fact for methods with decorators it doesn't handle,
  such as `@lru_cache`, so nothing contradicted the guess, and the engine filled the gap with the majority value. An
  answer can be statistically sound given the facts and still be wrong about the code, when the extractor failed to
  represent something. State "other" values explicitly rather than leaving them out (`docs/BUILDING_A_LAYER.md`).
- **Exceptions can go unanswered or wrong.** When a general rule and an exact specific rule disagree, the general
  one can win the vote. In both codebases, `classmethod` and `staticmethod` methods got a wrong answer labelled
  tendency, or no answer at all. They were never answered wrongly at law tier.
- **Settings found on one dataset are evidence, not a default.** The tuned configuration for the standard library
  held up on a second codebase, but `TENDENCYSTEPS 0` cut the score from 0.380 to 0.118 on the tokenomics data.
  Validate on your own held-out facts.

## Reading the rules

`e.rules()` reports each rule's matches (`n`), stated conclusions (`k`), `rate`, `lift`, agreement on known cases
(`agree` of `known`), and `tier`.

**Distrust a rule, or the setting that admitted it, when:**
- **`known` is tiny next to `n`.** "A function inherits its module's imports": 80 known of 98,782. It produced 93%
  of all derived facts.
- **It is law tier with low agreement.** `recommends(a,b) ⇒ depends on(b,a)` at 15% drove the dpkg flood.
- **`lift` is near or below 1.** The rule predicts the base rate.
- **The extractor guarantees it.** If the extractor only records same-module calls, "callers share the callee's
  module" is true by construction.

**Trust it more when** agreement is high on many known cases, such as Unicode case pairs (0.98 on 589) or code call
locality (0.82 on 10,372).

## When not to infer at all

- **Too few facts per relation** (under about 3 per name): nothing generalizes. The small services table produced
  only wrong facts.
- **Legal or safety decisions on tendency-tier answers.** Use `strict=True`, and show the proof to a person.
- **Anything you can compute exactly with a query.** The engine finds regularities. It doesn't replace a dependency
  solver or a database join.

## Agents (MCP)

`egm mcp` defaults to strict answers. In the recorded sessions (`docs/AGENT_SESSIONS.md`), Sonnet asked strictly
first and relaxed strictness only when it needed tendencies, and said so in its answer. Serve the knowledge base with
the settings you chose above, for example `egm mcp facts.txt --set MAXWORDS=50000 --set COVERAGE=0`.
