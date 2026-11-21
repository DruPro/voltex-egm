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
| `egm.shard(facts, shards, graph=..., ...)` | Several engines on parts of the data, one answer set (see [Sharding](#sharding-data-too-large-for-one-engine-egmshard)). |

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
| `explain(pattern)` | `str` or `None`: why there is no answer. |
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

For large vocabularies (more than a few thousand distinct words), add `"CLUSTERSTREAM": 1`. It gives the same answers
with far less memory; see `docs/SETTINGS.md`.

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

## Sharding: data too large for one engine (`egm.shard`, experimental)

> **Experimental, and not yet shown to be general.** Every result below comes from one synthetic world shape (the
> company world), which happens to contain a relation the noise never touches. You must name that relation
> (`graph`), and nothing tells you whether you chose well. It has not been tested on other world shapes or real
> data; a study of that is under way (`studies/shard_general`). Compare with one engine on a sample before relying
> on it.

One engine's memory grows faster than its facts. `egm.shard` splits the facts over several unchanged engines and
returns the union of their answers. It is the recipe measured in `studies/shard`.

```python
import egm
r = egm.shard("facts.txt", 16, graph=["collaborates with"], attach=["works under"], jobs=8)
for f in r.facts:            # Fact(status="inferred", tier="law" | "tendency"), as from infer_all()
    ...
print(r.warnings)            # [] when nothing was lost; otherwise what and why
print(r.report["engines"])   # per engine: facts, derived, seconds
print(r.report["consensus_dropped"], r.report["minority_rules"])
```

| Argument | Meaning |
|---|---|
| `facts` | a facts file, or a list of fact lines (one-word names, as everywhere) |
| `shards` | how many engines |
| `graph` | relations that define the split: each connected component of their graph goes to one shard. **Choose relations your noise can't corrupt.** |
| `attach` | relations that place an unassigned entity in the one shard all its assigned neighbours share (a team lead through `works under`) |
| `key` | instead of `graph`: split each subject of this relation by its object. Kept for comparison: if that relation can be wrong, precision falls. |
| `consensus` | default `True`: keep an answer only if the rule behind it was accepted by more than half the non-empty shards (and its derived premises survive too) |
| `central` | default `False`: one more engine learns from the reference facts and passes its law-tier conclusions to every shard |
| `settings` | engine settings for every engine. `MAXWORDS` is sized per engine (12000, or its vocabulary + 1000) unless you set it. |
| `jobs` | engines run at once; the answers don't depend on it |
| `workdir` | keep the shard files and engine outputs there (default: a temporary directory) |

**How facts are routed.**
- A fact goes to the shard of its subject, else of its object.
- A fact whose subject and object are both unassigned is reference data (teams, departments, cities). It goes to
  every shard that mentions its subject, followed from subject to object.
- A fact no shard mentions reaches no engine. That is reported in `warnings` and `report["unseen_facts"]`;
  `central=True` makes the central engine learn from such facts.

**What was measured** (company world, `studies/shard`):
- **Answers:** with a clean `graph` relation and consensus, identical to one engine at every size tested:
  - 61,108, 122,042 and 244,444 facts;
  - clean and 15% noise;
  - 4 to 16 shards;
  - 21 of 21 confirmatory runs.
- **Cost:** at 244,444 clean facts with 16 shards, one engine took 47.3 s of CPU and 8,350 MB; sharded with
  consensus, 22.7 s and 254 MB per engine (mean of 3 seeds).
  - With 15% noise: 41-43 s against 21.6-21.8 s and 266 MB.
  - `jobs=8` brought the wall time from 22.9 to 9.5 s.
- **Gate:** the helper reproduces the study harness's recorded answers in 27 of 27 runs (every arm, 2-16 shards,
  `studies/shard/tools/gate_sdk.py`).
- **Without consensus,** 16 shards (or small shards) under noise let borderline tendency rules through: up to 241
  wrong answers. Consensus removed every one, and changed nothing on clean data. It costs a second engine session per
  shard: about 2× the CPU, still below one engine.
- **A noisy split relation** (`key="is on"` with 15% of teams wrong) gave precision 0.876 against one engine's 1.000,
  with or without consensus. The split itself has to be right.

**Limits.**
- It was shown on synthetic data with a known clean relation. Which relations are clean is a property of your
  sources, and the helper can't check it.
- Each shard learns its own rules. A rule that needs evidence from many shards, and appears in none on its own,
  is lost (`central=True` covers rules about reference data).
- Before relying on a split, compare `egm.shard(...)` with one engine on a sample that still fits in one.

## Tuning settings to a dataset (`egm.tune`, experimental)

```python
import egm
r = egm.tune("facts.txt")               # hides 15% of the stated facts 3 times, keeps a change only if it helps every time
print(r.report())                       # e.g. "SET TREES 1", or "keep the defaults"
with egm.open("facts.txt", settings=r.settings) as e: ...
r = egm.tune("facts.txt", labels=open("verified.txt").read().splitlines())   # score on facts you verified elsewhere
```

```
egm tune facts.txt -o tuned.json          # prints every value tried
egm build facts.txt -o kb.vtx --settings tuned.json
```

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
