# The engine at its best: exact facts from one large codebase

Source: `studies/strengths` (pre-registered, three rounds; charts and proofs in `studies/strengths/report/index.html`).
The stress findings (`docs/STRESS_FINDINGS.md`) show where the engine fails on noisy extractions scored against a
partial key. This page shows the case it is built for:
- **Exact input:** facts that are exactly true, extracted deterministically by a parser.
- **Real rules:** rules that really hold in the data.
- **Complete truth:** every answer is checked against the full truth, so a correct answer can't count as wrong for
  being outside the key.

## The setup

- **Codebase:** the CPython 3.13.7 standard library, tests excluded: 273,430 lines in 534 files.
- **Extraction:** read with Python's `ast` only (`studies/strengths/tools/extract.py`). Base facts:
  - `inherits from`, `is a base of`;
  - `is a method of`, `is defined in`, `is part of`;
  - `has scope`, `has decorator`, `is first argument of`.
- **Three questions,** each needing a different kind of reasoning:

  | Target | What it is | Reasoning it needs |
  |---|---|---|
  | `C is a subclass of A` | every ancestor of a class | depth: chained inference rounds |
  | `m belongs to package P` | method → class → module → package | a 3-premise rule (`CHAIN 3`) |
  | `f__a0 is bound to self/cls/nothing` | what Python passes as the first argument | a tree: scope and decorator together (`TREES 1`) |

- **Hidden:** 5,901 of these facts. No rules were given.

## Result

With `TREES 1`, `CHAIN 3`, `DEPTH 0` and `TENDENCYSTEPS 0` (and `MAXWORDS` sized). Ingesting the facts took
0.2 s. Learning the rules and inferring took 10.4 s, once, on the first question;
most of that is the tree search. Peak memory was 210 MB.

| | |
|---|---|
| Hidden facts recovered | **5,829 of 5,901 (98.8%)** |
| Law-tier answers correct | **5,829 of 5,829** |
| Wrong answers | 21, every one labelled *tendency*, so `ask(..., strict=True)` returns none |
| Facts invented in other relations | 0 |

Each setting unlocks one kind of reasoning; recall without → with it:

| Reasoning | Without | With |
|---|---|---|
| Ancestry with 70% of classes hidden, `DEPTH` 1 → 0 | 0.965 | 1.000 |
| Package of a method, `CHAIN` 2 → 3 | 0.000 | 1.000 |
| First-argument binding, `TREES` 0 → 1 | 0.000 | 0.981 |

## Depth: five generations, built in three rounds

Exploratory stress: the ancestry of 70% of classes is hidden, so a class's parents are often hidden too. Recall by
`DEPTH`:

| `DEPTH 1` | `DEPTH 2` | `DEPTH 3` | `DEPTH 0` (to the end) |
|---|---|---|---|
| 0.9651 | 0.9988 | 1.0000 | 1.0000 |

There are 0 wrong facts at every depth. Each round builds on the facts the round before derived:

```
logging.handlers.RotatingFileHandler is a subclass of logging.Filterer [law]
├── logging.handlers.RotatingFileHandler is a subclass of logging.Handler [law]
│   ├── logging.handlers.RotatingFileHandler is a subclass of logging.FileHandler [law]
│   │   ├── logging.handlers.RotatingFileHandler inherits from logging.handlers.BaseRotatingHandler (stated)
│   │   └── logging.handlers.BaseRotatingHandler inherits from logging.FileHandler (stated)
│   └── logging.FileHandler is a subclass of logging.Handler [law]
│       ├── logging.FileHandler inherits from logging.StreamHandler (stated)
│       └── logging.StreamHandler inherits from logging.Handler (stated)
└── logging.Handler inherits from logging.Filterer (stated)
```

## Multi-premise: three hops, no shortcut

No fact links a method to its package. The rule had to be learned as a three-premise path:

```
asyncio.base_events.BaseEventLoop._add_callback belongs to package asyncio [law]
├── asyncio.base_events.BaseEventLoop._add_callback is a method of asyncio.base_events.BaseEventLoop (stated)
├── asyncio.base_events.BaseEventLoop is defined in asyncio.base_events (stated)
└── asyncio.base_events is part of asyncio (stated)
```

## Trees: Python's binding rules, learned from the code

The engine was never told what a decorator does. These are the binding rules it accepted:

| Rule | Agreement | Known cases |
|---|---|---|
| `[? is first argument of ?](a,g) & [? has decorator ?](g,classmethod) => [? is bound to ?](a,cls)` | 1.00 | 116 |
| `[? is first argument of ?](a,g) & [? has decorator ?](g,staticmethod) => [? is bound to ?](a,nothing)` | 1.00 | 55 |
| `[? is first argument of ?](a,g) & [? has scope ?](g,module) => [? is bound to ?](a,nothing)` | 1.00 | 1,919 |
| `[? is first argument of ?](a,g) & [? has decorator ?](g,property) => [? is bound to ?](a,self)` | 1.00 | 309 |
| `[? is first argument of ?](a,g) & [? has scope ?](g,class) => [? is bound to ?](a,self)` | 0.97 | 6,517 |

A method with no decorator:

```
ast._Unparser._write_str_avoiding_backslashes.a0 is bound to self [law]
├── ast._Unparser._write_str_avoiding_backslashes.a0 is first argument of ast._Unparser._write_str_avoiding_backslashes (stated)
└── ast._Unparser._write_str_avoiding_backslashes has scope class (stated)
```

A property:

```
bz2.BZ2File.mode.a0 is bound to self [law]
├── bz2.BZ2File.mode.a0 is first argument of bz2.BZ2File.mode (stated)
└── bz2.BZ2File.mode has decorator property (stated)
```

A module-level function:

```
argparse._get_action_name.a0 is bound to nothing [law]
├── argparse._get_action_name.a0 is first argument of argparse._get_action_name (stated)
└── argparse._get_action_name has scope module (stated)
```

## What it gets wrong, and how it says so

The 72 hidden facts about `classmethod` and `staticmethod` methods are the exceptions to "methods bind `self`". The
exact rules for them were learned, at 1.00 agreement. But in packages where almost every method binds `self`, the
general rules outvote them. 21 came out wrong, and each is labelled tendency:

```
asyncio.windows_events.IocpProactor._finish_recvfrom.a0 is bound to self [tendency]
├── asyncio.windows_events.IocpProactor._finish_recvfrom.a0 is first argument of asyncio.windows_events.IocpProactor._finish_recvfrom (stated)
└── asyncio.windows_events.IocpProactor._finish_recvfrom belongs to package asyncio (stated)
```

The other 51 got no answer. The vote is part of the inference decision stack; preferring the more specific rule is
noted for the owner in `studies/strengths/RESULTS.md`.

## Replication on a second, independent codebase

This was pre-registered before any run on the data (`PREREGISTRATION_REPLICATION.md`), with the same settings and no
tuning on this data.
- **Codebase:** Debian's Python packages (`/usr/lib/python3/dist-packages`), 1,027,745 lines of
  third-party code, with ancestry up to 13 ancestors.
- **Size:** 171,223 facts, with 17,635 hidden.

| | |
|---|---|
| Hidden facts recovered | **17,271 of 17,635 (97.9%)** |
| Law-tier answers true | **17,265 of 17,269** |
| Package of a method, `CHAIN` 2 → 3 | 0.000 → 1.000 |
| First-argument binding, `TREES` 0 → 1 | 0.000 → 0.961 |
| Ingest; learning and inference (once, on the first question); each question after | 0.82 s; 39.1 s; 0.71 ms median, 2.63 ms max over 100 (`tools/query_time.py`) |

Verdicts: X1 fail, X2 pass, X3 pass, X4 pass, X5 pass.

**X1 failed on 4 law-tier answers**, all of the form "this method has no decorator", and all false. The extractor
wrote no decorator fact for methods whose decorators it doesn't handle (`@lru_cache` and the like). Nothing
contradicted the majority value, so the engine filled the gap with it. Given the facts, the answer was statistically
sound; about the code, it was wrong. The lesson is for extraction: write `has decorator other` instead of nothing.

The exception problem replicates too. Of the 370 hidden `classmethod` and `staticmethod` facts, 6 are right, 84 wrong
(all labelled tendency) and 280 unanswered.

## What this does and doesn't show

- **It shows** that on exact code facts, the engine learns the code's own rules and answers with proofs. On two
  codebases, nearly every law-tier answer was true, and it labels its guesses as such.
- **It doesn't show** that these settings are best everywhere. On the stdlib facts, an expanded `egm.tune` search
  found the hand-chosen configuration from the data alone. That recovers the parameters for that dataset; it isn't
  a universal default. On the tokenomics data, `TENDENCYSTEPS 0` lowered the score from 0.380 to 0.118. Validate on
  your own held-out facts.
- **Law tier means reliable given what was observed.** An extractor that leaves something out can make a law-tier
  answer wrong about the real system.
- **An empty answer means unknown, not false.** `egm mcp` and `explain()` say so, and name any cap.

## What made the difference

The same code went through three pre-registered rounds:

| Round | What changed | Precision | Recall |
|---|---|---|---|
| 1 | facts stated naively | 1.000 | 0.276 |
| 2 | the same ast facts, in the engine's rule language | 0.043 | 0.988 |
| 3 | plus `TENDENCYSTEPS 0`, the guide's setting for answers you act on | 0.996 | 0.988 |

1. **State facts the rule shapes can express.**
   - **No copy shape:** a rule can't copy one relation into another in the same direction, so state the inverse too
     (`B is a base of C`).
   - **Trees need an anchor:** give them one entity to hang from (`f__a0 is first argument of f`).

   See `docs/DATA_DESIGN.md`, section 2.
2. **On exact data, keep only law-tier proofs.** In round 2, every law-tier rule was true of Python; all the wrong
   facts came from tendencies.
3. **Size `MAXWORDS`** to the vocabulary (27,398 words here).

Reproduce: `python3 studies/strengths/tools/extract.py --r2`, then
`ROUND=3 python3 studies/strengths/tools/run.py full TREES=1 CHAIN=3 DEPTH=0`.
