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
