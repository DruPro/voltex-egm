# EGM Python SDK reference (2.2.1)

    pip install .            # from the kit: compiles the engine into the package, installs `egm`

Python 3.8+, no dependencies. Needs a C++17 compiler at install time (`CXX` picks one). To use a
prebuilt engine instead: `EGM_SKIP_ENGINE_BUILD=1 pip install .`, then set `VOLTEX=/path/to/voltex2`.

```python
import egm

with egm.open("kb.vtx") as kb:                   # saved knowledge base, or a facts .txt file
    for f in kb.ask("? calls mypkg__connect"):
        print(f.subject, f.status, f.tier, f.because)
    kb.values("mypkg__Client raises ?", strict=True)   # -> ['mypkg__AuthError', ...]
```

An `Engine` is one running `voltex2` process. The knowledge base loads once, and each call after
that is a pipe round trip (well under a millisecond on the example corpora). An `Engine` is not
thread-safe: use one per thread, or guard it with a lock.

## Opening

| Call | Does |
|---|---|
| `egm.open(path, **kw)` | `.vtx`: load it. `.txt`: ingest it. Same as `Engine.open`. |
| `egm.Engine(kb=None, facts=(), binary=None, settings=None)` | Start an engine, optionally loading `kb`, ingesting `facts` files, applying `settings` (e.g. `{"RATE": 0.4}`). |
| `egm.find_binary(path=None)` | Where the engine is: `path` > `$VOLTEX` > bundled > `build/` > `PATH`. |
| `egm.shard({source: facts, ...})` | One engine per independent source, one answer set tagged by source (see [Several engines](#several-engines-one-answer-set-egmshard-experimental)). |

Use `with` (or call `close()`). `kb.closed` tells you whether the process has exited.

## Adding evidence

| Method | Returns | Notes |
|---|---|---|
| `ingest(fact)` | `int` id | The same text always gets the same id. |
| `ingest_many(facts)` | `int` count | One round trip for any number of facts. Blank lines are skipped. |
| `ingest_file(path)` | engine lines | One fact per line. |
| `observe(source, record, time, revision=1, scope="snapshot", facts=())` | `None` | `snapshot`: `facts` is everything `record` says now, and what it stopped saying becomes history. `partial`: add only. |
| `retract(fact)` | `bool` | `False` if it wasn't stored. |
| `update(fact)` | engine lines | Replace the subject's old value in a one-value relation. |

Facts are `A relation B` with no spaces inside a name. A relation is learned once it has **at least
3 facts with at least 2 different names in each slot**.

## Asking

| Method | Returns |
|---|---|
| `ask(pattern, strict=False, require=False)` | `list[Fact]`: everything the engine says about the pattern, including history. |
| `current(pattern, strict=False)` | `list[Fact]`: only what holds now. |
| `history(pattern)` | `list[Fact]`: only past values. |
| `values(pattern, strict=False)` | `list[str]`: the filled slot of each current answer, sorted. |
| `explain(pattern)` | `str` or `None`: why there is no answer: an unlearned relation, or `unknown_note()`. |
| `unknown_note()` | What an empty answer means: unknown, not false; under a `[LIMIT]` cap it names the cap, since the answer may lie beyond it. |
| `infer_all()` | `list[Fact]`: every fact the accepted rules derive. |
| `conflicts()` | `list[Conflict]`: stated facts the rules contradict, plus source disagreements. |

`?` marks the slot to fill: `"? calls x"` asks for subjects, `"x calls ?"` for objects.

**`strict=True`** keeps stated and current facts plus `law`-tier inferences, and drops `tendency`
inferences. Use it when a wrong answer costs more than a missing one.

**`require=True`** raises `RelationNotLearned` instead of returning `[]` when the relation hasn't been
learned, so a typo or a cold start doesn't look like "no answer".

### `Fact`

| Field | Meaning |
|---|---|
| `fact`, `subject`, `relation`, `object` | The fact and its three parts. |
| `status` | `stated`, `current` (the new value after a change), `inferred`, or history: `historical`, `corrected`, `superseded`, `withdrawn`. |
| `flag` | `""` or `stale`, `sources_disagree`, `uncertain`, `contradicted`, `current_unknown`. |
| `tier`, `score` | For inferences: `law` or `tendency`, and the rule's score. |
| `because`, `rule` | The proof: the facts the inference used, and the rule that combined them. |
| `source` | The source that stated it (facts added through `observe`). |
| `note` | The engine's explanation: who disagrees, when a value held, why something is stale. |
| `raw` | The engine's line, unparsed. |

Properties: `is_current`, `is_history`, `is_strict`. `to_dict()` is JSON-ready.

## What was learned

| Method | Returns |
|---|---|
| `relations()` | `list[Relation]`: `template`, `relation`, `facts` (count). |
| `rules(include_rejected=False, shape=None)` | `list[Rule]`: `text`, `accepted`, `n` (chains seen), `k` (conclusion also stated), `rate`, `lift`, `known`, `agree`, `tier`, `shape` (`inverse`, `chain`, `path`, `tree`), `premises`, `condition` (set for a rule restricted to a group). `shape=` filters. |
| `experimental()` | `dict` of experimental settings currently on, e.g. `{"TREES": 1}`. |
| `categories(threshold=None)` | `list[Category]`: word classes induced from shared contexts. |
| `metrics()` | `dict`: records, vocabulary, grammar size, memory. |

## Sequence model

| Method | Returns |
|---|---|
| `predict(prefix)` | `list[Prediction]`: next words, with `p` and `observed` (`False` = inferred via categories). |
| `query(pattern)` | `list[Prediction]`: slot fillers by sequence statistics, not rules. |
| `generate(prefix="")` | `str`: a continuation sampled from the grammar (deterministic for a given state). |
| `sample(n=5)` | `list[str]`: `n` sampled sentences. |

## Records, settings, persistence

`find(text) -> int | None`, `text in kb`, `unroll(id) -> str`, `set(key, value)` (raises `ValueError`
for an unknown key), `save(path)`, `load(path)`, `version()`, and `cmd(line) -> list[str]` for any
raw engine command. `save` writes `path` plus `path.obs` (the observation log); keep them together.

## Errors

All derive from `egm.EgmError`.

| Exception | Also a | When |
|---|---|---|
| `EngineNotFound` | `FileNotFoundError` | No `voltex2` binary found. |
| `EngineError` | `RuntimeError` | The engine rejected a command, couldn't load or save, exited, or is older than 2.2.1. |
| `RelationNotLearned` | `LookupError` | `ask(..., require=True)` on an unlearned relation. Has `.relation` and `.learned`. |

Bad arguments (a space in a source name, an unknown scope, a newline in a command) raise `ValueError`.

## Evaluation helpers

```python
from egm import bench
from egm.extract_python import extract, write

facts = extract(["mypkg=path/to/mypkg"])          # {relation: {(a, b), ...}}, static, never runs code
write(facts, "mypkg.txt", "mypkg.truth.json")
truth = {r: sorted(v) for r, v in facts.items()}
key = bench.make_questions(truth, seed=7)          # questions with answers; bench.public(key) strips them
with egm.open("mypkg.txt") as kb:
    report = bench.score(key, bench.solve(kb, key, strict=True))
print(report["mean_f1"], report["by_kind"])
```

`bench.score` takes answers from anywhere (`[{"id": ..., "answer": ...}]`), including answers an LLM
wrote, so you can compare a model and EGM on the same key.

## Example: an agent tool

```python
import json, egm

kb = egm.open("mypkg.vtx")

def egm_tool(pattern: str, strict: bool = True) -> str:
    """Give this to an LLM as a tool: it asks EGM instead of rereading source code."""
    try:
        facts = kb.ask(pattern, strict=strict, require=True)
    except egm.RelationNotLearned as e:
        return json.dumps({"error": str(e), "learned": e.learned})
    return json.dumps([{k: f.to_dict()[k] for k in ("fact", "status", "tier", "because")} for f in facts])
```

## Experimental settings

All are off by default and saved with the knowledge base (`docs/SETTINGS.md`).

Large vocabularies need no setting for memory: `CLUSTERSTREAM` is on by default (`docs/SETTINGS.md`). Size `MAXWORDS`
to the vocabulary.

```python
import egm
with egm.open("gates.txt", settings={"TREES": 1, "DEPTH": 0}) as e:
    for r in e.rules(shape="tree"):
        print(r.premises, r.text)        # TREE [? is output of ?](a,g) & [? has kind ?](g,or) & ...
    f = [x for x in e.ask("w17 has value ?") if x.status == "inferred"][0]
    print(f.rule, f.because)             # the tree rule and every premise fact
    print(e.experimental())              # {'TREES': 1}
```

| Setting | What the SDK shows |
|---|---|
| `DEPTH` | more facts from `infer_all()`; `0` runs to a fixpoint |
| `CHAIN` 3-8 | rules with `shape == "path"` and `premises == CHAIN`; facts with that many `because` entries |
| `CONDITIONS` | rules with `condition` set, e.g. `[? works as ?](a,farmer|miner)` |
| `TREES` | rules with `shape == "tree"`, text starting `TREE `; facts whose `because` lists every branch |

The tests in `tests/test_sdk.py` (`TestExperimentalSettings`) run each one on a small world from
`tests/worlds.py`. The MCP tool `egm_relations` reports each rule's `shape`, `premises` and
`condition`, and `experimental_settings` when any is on.

## Several engines, one answer set (`egm.shard`, experimental)

`egm.shard` runs several unchanged engines and returns the union of their answers. **Its use is independent
sources:** fact sets that don't describe the same entities and shouldn't share rules, such as separate codebases,
customers or domains.

**It is not the way to handle large data.** One engine (with `CLUSTERSTREAM`, on by default; `docs/SETTINGS.md`) handled 244,444
facts in 256 MB and 19 s, with exact answers. Splitting one fact set changes what is learned, because each engine
decides which rules to accept from its own part of the evidence (see "Splitting one fact set" below).

### Independent sources (recommended use)

```python
import egm
r = egm.shard({"billing": "billing_facts.txt",       # a facts file ...
               "search": search_lines},               # ... or a list of fact lines
              jobs=2)
for f in r.facts:
    print(f.fact, f.tier, f.source)                   # e.g. "x calls y  law  billing"
print(r.warnings)                                     # [] when the sources are independent and nothing hit a limit
print(r.report["sources"])                            # per source: facts, derived, seconds
```

**What happens:**
- **One engine per source.** Nothing is routed between sources, so each learns its own rules from its own facts.
  Rules can't form from coincidences across unrelated sources, and one source's noise can't reach another.
- **The answers are the union.** Each `Fact.source` names the source that derived it (comma-separated if several
  derived the same fact). A fact derived as law by any source is reported as law.
- **Every source gets the same `settings`.** `MAXWORDS` is sized to each source's vocabulary unless you set it.
  Sources that need different settings are a reason to run separate engines yourself (`egm.open` per source).
- **`jobs`** runs sources at the same time; the answers don't depend on it.
- **`consensus` is off by default here.** Turn it on (`consensus=True`) only if the sources are samples of the same
  rules and you want an answer kept only when most sources accepted its rule.

**Warnings to act on:**

| Warning | What it means | What to do |
|---|---|---|
| `N entities appear in more than one source` | The sources describe some of the same entities, so they aren't independent. Each source answers about those entities from its own facts only. | If the overlap is real (the same entity), use one engine over all the facts: that is the exact answer. If it's a naming clash, make names unique per source (e.g. a prefix). |
| `source(s) have no facts` | An empty source was skipped. | Check the input. |
| `<source>: [LIMIT] ...` | A capacity cap was hit in that source's engine. | Raise the named setting (`MAXWORDS`, `MAXRELATIONS`). |

**When not to use it:**
- **The data is one connected domain that is just large.** Use one engine (`CLUSTERSTREAM` is on by default); size `MAXWORDS` to the vocabulary.
- **You need answers that combine facts from several sources** (a call in one codebase to a function defined in
  another). The sources aren't independent, so use one engine.
- **The sources need different settings, or you want to keep each knowledge base.** Run `egm.open` per source and
  save each one.

**Checked by:**
- `tests/test_sdk.py` `TestShardSources`: each source's answers equal a separate engine's on that source, tagged
  with the source; shared entities are reported; consensus is opt-in.
- The answers of each source can't depend on the other sources, because no fact is routed between them.

### Splitting one fact set (experimental, not general)

```python
r = egm.shard("facts.txt", 8, graph=["collaborates with"], attach=["works under"])   # consensus on by default
```

| Argument | Meaning |
|---|---|
| `shards` | how many engines |
| `graph` | relations whose connected components define the split (each component goes to one shard) |
| `attach` | relations that place an unassigned entity in the one shard all its assigned neighbours share |
| `key` | instead of `graph`: split each subject of this relation by its object |
| `consensus` | default `True`: keep an answer only if more than half the non-empty shards accepted its rule |
| `central` | default `False`: one more engine learns from the reference facts and passes its law-tier conclusions to the shards |

**Routing:**
- A fact goes to its subject's shard, else its object's.
- Facts about entities in no shard are reference data. They go to every shard that mentions them, followed from
  subject to object.
- Facts that reach no shard are reported in `warnings` and `report["unseen_facts"]`.

**Why it is not general.** Sharded answers equal one engine's only if the split does two things:
- it keeps each fact's evidence together (locality);
- it leaves every shard a fair sample of every rule's evidence (representativeness), because each shard decides
  alone which rules to accept.

In `studies/shard_general` (6 worlds, 36 runs):
- **Automatic split** (derived from the data, no relation names): matched one engine on company data without noise
  and on family trees, and nowhere else. It failed on noisy company data, the blind world, gate circuits and real
  code, because it clusters around shared values (cities, gate kinds), so its shards are skewed samples.
- **Random split:** failed everywhere, because it breaks locality.
- **User-named split on the company world:** identical to one engine in every run (`studies/shard`: 61,108 to
  244,444 facts, clean and 15% noise, 4-16 shards). It has both properties.

Nothing checks that your split has them. Compare with one engine on a sample before relying on it.

**Known flaw:** consensus compares rule texts, so the same rule written with its premises in another order counts as a
different rule (seen with `TREES`).

## Tuning settings to a dataset (`egm.tune`, experimental)

```python
import egm
r = egm.tune("facts.txt")               # hides 15% of the stated facts 3 times, keeps a change only if it helps every time
print(r.report())                       # e.g. "SET TREES 1", or "keep the defaults"
with egm.open("facts.txt", settings=r.settings) as e: ...
r = egm.tune("facts.txt", labels=open("verified.txt").read().splitlines())   # score on facts you verified elsewhere
r = egm.tune("facts.txt", settings={"MAXWORDS": 50000})   # start every candidate from a base configuration
r = egm.tune("facts.txt", expanded=True)  # opt-in wider search, about 2.6x the cost (below)
with egm.open("facts.txt", settings=r.all_settings) as e: ...   # base + changes (r.settings lists only the changes)
```

```
egm tune facts.txt -o tuned.json          # prints every value tried
egm tune facts.txt --expanded --set MAXWORDS=50000 -o tuned.json
egm build facts.txt -o kb.vtx --settings tuned.json
```

**The default search** (`egm.tune.DEFAULT_SPACE`) is unchanged and lightweight. **`expanded=True`** (`--expanded`)
searches `egm.tune.expanded_space(facts)`. That is the default space plus `TENDENCYSTEPS` (-1, 0), `DEPTH` 1 and 2,
and `MAXWORDS` sized from the data's own vocabulary when it exceeds the default cap. Every value is an engine
default or derived from the data.
- **On the Python standard library facts** (`studies/strengths/tune`, exploratory), the default search adopted only
  `RATE 0.5`, taking F0.5 from 0.034 to 0.276. The expanded search adopted `TENDENCYSTEPS 0`, `CHAIN 3`, `TREES 1`
  and a sized `MAXWORDS`, reaching 0.733. That is the configuration chosen by hand for that study.
- **What it shows:** the search recovers the right parameters on that dataset. It doesn't show that the
  configuration is best everywhere. On the tokenomics S set, the same search started from `TENDENCYSTEPS 0` put it
  back to -1, because law-only proofs cut the score there from 0.380 to 0.118.

Tuning changes only setting values, never the engine, and the chosen values are saved with the
knowledge base. What `studies/noise` measured:

- **Structural switches are found.** Holdout tuning turned on `TREES` for gate data and `CHAIN 3`
  for family trees in every seed (12 of 12), with large gains. In 36 runs it never scored below the
  defaults on the hidden answers.
- **Fixes for wrong facts are not visible to holdout tuning.** It hides stated facts, and some of
  those are themselves wrong, so it cannot reward a setting that corrects them. With 30% wrong
  facts, `QUARANTINE` scored +0.000 to +0.001 on the holdout and +0.023 to +0.029 on the truth.
  Verified `labels` do show it (company world: F0.5 0.941 to 0.987), but small label sets can
  also overfit (two hidden-world runs ended 0.0003 and 0.002 below the defaults).
- **Settings are dataset-specific.** `CHAIN 3`, tuned on family trees, lowered another world from
  0.775 to 0.636. Tune each dataset; don't copy settings between them.

New fields: `Rule.replication` (why `REPLICATE` rejected a rule), `Conflict.kind` (`value`,
`quarantined`, `outvoted`, `other`), and the ASK flags `outvoted` and `quarantined`.

## Proof chains and limits

```python
with egm.open("facts.txt") as e:
    e.chains()      # [{"fact": "...", "round": 2, "tendency_steps": 1}, ...]: how each derived fact was reached
    e.limits()      # capacity limits the build hit, e.g. ["categories cover the 12000 most frequent of 16016 words; ..."]
with egm.open("facts.txt", settings={"TENDENCYSTEPS": 0}) as e:
    e.infer_all()   # only answers whose whole proof uses law-tier rules
```

Count `chains()` by round and tendency steps before choosing `TENDENCYSTEPS`. It shows whether
your answers rest on tendencies, and whether a single tendency is being amplified over later rounds.
