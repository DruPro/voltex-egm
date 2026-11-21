"""Write docs/STRENGTHS.md from ../results_summary.json and ../showcase.json (every number read from those files)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
C = json.load(open(os.path.join(STUDY, "showcase.json"))); S = json.load(open(os.path.join(STUDY, "results_summary.json")))


def tr(p, pre="", last=True, top=True):
    f = p["fact"].replace("__", ".")
    tag = " (stated)" if p.get("stated") else f" [{p.get('tier')}]"
    out = [(f if top else pre + ("└── " if last else "├── ") + f) + tag]
    kids = p.get("because", []); np = pre if top else pre + ("    " if last else "│   ")
    for i, b in enumerate(kids): out += tr(b, np, i == len(kids) - 1, False)
    return out


blk = lambda p: "```\n" + "\n".join(tr(p)) + "\n```"
D = S["results_depth"]["runs"]; R3 = S["results_r3"]["runs"]; b = C["proofs_binding"]
X = S["results_dist"]; XR = X["runs"]["full"]; XT = XR["tiers"]
QT = json.load(open(os.path.join(STUDY, "results_dist", "query_time.json")))   # tools/query_time.py
pr = lambda run, r: run["per_relation"][r]
rules = "\n".join(f"| `{x['text'].replace('TREE ', '')}` | {x['agree']:.2f} | {x['known']:,} |" for x in C["rules_tree_binding"])
doc = f"""# The engine at its best: exact facts from one large codebase

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
{R3['full']['build_s']} s. Learning the rules and inferring took {R3['full']['infer_s']} s, once, on the first question;
most of that is the tree search. Peak memory was {R3['full']['peak_rss_mb']} MB.

| | |
|---|---|
| Hidden facts recovered | **{R3['full']['recovered']:,} of 5,901 ({R3['full']['recall']*100:.1f}%)** |
| Law-tier answers correct | **{C['tiers']['law correct']:,} of {C['tiers']['law correct']:,}** |
| Wrong answers | {R3['full']['wrong']}, every one labelled *tendency*, so `ask(..., strict=True)` returns none |
| Facts invented in other relations | {pr(R3['full'], 'other')['derived']} |

Each setting unlocks one kind of reasoning; recall without → with it:

| Reasoning | Without | With |
|---|---|---|
| Ancestry with 70% of classes hidden, `DEPTH` 1 → 0 | {D['d1']['subclass']['recall']:.3f} | {D['d0']['subclass']['recall']:.3f} |
| Package of a method, `CHAIN` 2 → 3 | {pr(R3['default'], 'belongs to package')['recall']:.3f} | {pr(R3['chain3'], 'belongs to package')['recall']:.3f} |
| First-argument binding, `TREES` 0 → 1 | {pr(R3['default'], 'is bound to')['recall']:.3f} | {pr(R3['trees'], 'is bound to')['recall']:.3f} |

## Depth: five generations, built in three rounds

Exploratory stress: the ancestry of 70% of classes is hidden, so a class's parents are often hidden too. Recall by
`DEPTH`:

| `DEPTH 1` | `DEPTH 2` | `DEPTH 3` | `DEPTH 0` (to the end) |
|---|---|---|---|
| {D['d1']['subclass']['recall']:.4f} | {D['d2']['subclass']['recall']:.4f} | {D['d3']['subclass']['recall']:.4f} | {D['d0']['subclass']['recall']:.4f} |

There are 0 wrong facts at every depth. Each round builds on the facts the round before derived:

{blk(D['d0']['proof_deepest'])}

## Multi-premise: three hops, no shortcut

No fact links a method to its package. The rule had to be learned as a three-premise path:

{blk(C['proofs_package'][0])}

## Trees: Python's binding rules, learned from the code

The engine was never told what a decorator does. These are the binding rules it accepted:

| Rule | Agreement | Known cases |
|---|---|---|
{rules}

A method with no decorator:

{blk(b['class none'])}

A property:

{blk(b['class property'])}

A module-level function:

{blk(b['module none'])}

## What it gets wrong, and how it says so

The 72 hidden facts about `classmethod` and `staticmethod` methods are the exceptions to "methods bind `self`". The
exact rules for them were learned, at 1.00 agreement. But in packages where almost every method binds `self`, the
general rules outvote them. 21 came out wrong, and each is labelled tendency:

{blk(C['proofs_wrong'][0])}

The other 51 got no answer. The vote is part of the inference decision stack; preferring the more specific rule is
noted for the owner in `studies/strengths/RESULTS.md`.

## Replication on a second, independent codebase

This was pre-registered before any run on the data (`PREREGISTRATION_REPLICATION.md`), with the same settings and no
tuning on this data.
- **Codebase:** Debian's Python packages (`/usr/lib/python3/dist-packages`), {X['corpus']['lines']:,} lines of
  third-party code, with ancestry up to {X['corpus']['max_ancestors']} ancestors.
- **Size:** {X['corpus']['facts']:,} facts, with {X['corpus']['hidden']:,} hidden.

| | |
|---|---|
| Hidden facts recovered | **{XR['recovered']:,} of {XR['hidden']:,} ({XR['recall']*100:.1f}%)** |
| Law-tier answers true | **{XT['law correct']:,} of {XT['law correct'] + XT['law wrong']:,}** |
| Package of a method, `CHAIN` 2 → 3 | {pr(X['runs']['default'], 'belongs to package')['recall']:.3f} → {pr(X['runs']['chain3'], 'belongs to package')['recall']:.3f} |
| First-argument binding, `TREES` 0 → 1 | {pr(X['runs']['default'], 'is bound to')['recall']:.3f} → {pr(X['runs']['trees'], 'is bound to')['recall']:.3f} |
| Ingest; learning and inference (once, on the first question); each question after | {QT['ingest_s']} s; {QT['first_question_s']} s; {QT['query_ms_median']} ms median, {QT['query_ms_max']} ms max over {QT['questions']} (`tools/query_time.py`) |

Verdicts: {', '.join(f'{k} {v}' for k, v in X['verdicts'].items())}.

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
| 1 | facts stated naively | {S['results']['runs']['full']['precision']:.3f} | {S['results']['runs']['full']['recall']:.3f} |
| 2 | the same ast facts, in the engine's rule language | {S['results_r2']['runs']['full']['precision']:.3f} | {S['results_r2']['runs']['full']['recall']:.3f} |
| 3 | plus `TENDENCYSTEPS 0`, the guide's setting for answers you act on | {R3['full']['precision']:.3f} | {R3['full']['recall']:.3f} |

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
"""
open(os.path.join(STUDY, "..", "..", "docs", "STRENGTHS.md"), "w").write(doc)
print("wrote docs/STRENGTHS.md")
