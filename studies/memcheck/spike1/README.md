# Memory-leak spike 1: one pattern, EGM vs static analyzers

**Question:** can EGM find a leak that the compiler and static analyzers miss, by learning a codebase's own
resource conventions from exact parser facts?

**Status:** a feasibility spike. The codebase was written by the same author as the detector, so the answer was
known in advance. It shows the mechanism works on one pattern; it is not evidence that it generalizes.

## The pattern: a leaked handle from an opaque library

`ctx_create()` and `ctx_destroy()` live in `ctx.c`. The app (`app.c`) sees only `ctx.h`, the normal situation for
any library API, file descriptor or pool handle. The codebase (`gen_code.py`) has 69 functions:

- 36 correct `ctx` users (create, use, destroy; early returns; two handles at once)
- 26 correct `buf` users (a second opaque API, `buf_new` / `buf_release`)
- 8 correct borrowers of a shared `ctx_default()`, which must **not** be destroyed
- 2 factories that return the handle, and 2 registries that store it in a struct field (ownership handed on)
- 1 leak, `report_usage()`: it creates a `ctx`, uses it and returns without destroying it

## Results

The engine and its settings were the same in every EGM run: default build, `TREES 1`, no code changes. Only the
facts changed.

**The tools, on the final facts:**

| Tool | How it was run | Leak found | False alarms |
|---|---|---|---|
| `gcc -Wall -Wextra` | normal build | no | 0 |
| clang static analyzer | normal build, per file | **no** | 0 |
| gcc `-fanalyzer` | normal build, per file | no | 0 |
| clang static analyzer | library and app merged into one file, so it can see the `malloc` | **yes** | 0 |
| gcc `-fanalyzer` | merged into one file | no | 2 (uninitialized value; looks spurious) |
| EGM, default policy | facts v4 | **yes** | **0** |
| EGM, strict policy | facts v4 | no: the rule fails strict's split-half replication test (not yet diagnosed) | 0 |

**What changed EGM's result: the facts, version by version** (`extract.py`):

| Facts | What was added | What EGM learned | Leak found | False alarms |
|---|---|---|---|---|
| v1 | calls, `comes from`, `is passed to`, `escapes via`; one API | nothing: every handle came from `ctx_create`, so EGM folded "comes from ctx_create" into the phrasing and the relation disappeared | no | 0 |
| v2 | a second API (`buf`) and a borrowed handle (`ctx_default`) | relations found, no rules: a release was one of many `is passed to` facts, and tree rules only conclude one-value relations | no | 0 |
| v3 | `h ends with <last call>` (one value per handle) and `X is source of h` | `buf_new → buf_release` 26/26 (law); `ctx_create → ctx_destroy` 46/51, agreement 0.90 (tendency) | yes | 4: the factories and registries, stated as "ending" with `ctx_set` |
| v4 | C's ownership semantics stated as facts: a returned or stored handle is handed on, so no ending is stated for it here | the same conventions; `ctx` becomes a law (46/47, agreement 0.98) | **yes** | **0** |

The v3 false alarms were a fact error: the extractor said a handed-on handle "ends with `ctx_set`", which is
false. Its life continues in the caller. Correcting the fact removed the alarms and also raised the rule from
tendency to law.

What EGM learned, with nothing telling it which function is a destructor:

- **`buf`:** `buf_new` handles end with `buf_release`.
- **`ctx`:** `ctx_create` handles end with `ctx_destroy`.
- **Borrowed handles:** the 8 `ctx_default` handles were never flagged, because the rule is anchored on where a
  handle comes from, not on its type.

The report is a conflict with a proof:

```
stated: report_usage__c ends with ctx_run | inferred: report_usage__c ends with ctx_destroy
because report_usage__c comes from ctx_create + ctx_create is source of ...  [rule: TREE ...]
```

## What it says

1. **Data quality decided the outcome; the engine didn't change.** Two kinds of fact matter:
   - **Universal semantics** (ownership transfer by return or store) are stated as exact facts by the extractor.
   - **Project conventions** (which call releases which handle, and which handles are borrowed) are what EGM
     learns. An analyzer can't learn those, and it can't see them through an opaque library.
2. **Is it better than a static analyzer? On this pattern: complementary.**
   - When the allocation is invisible (normal builds against a library), EGM finds the leak and the analyzers don't.
   - When the analyzer can see the allocation, it finds the leak with nothing to learn.

## Not tested yet

- Leaks on one path only (released on the normal path, leaked on an early error return): needs per-exit facts.
- Aliasing (the handle copied to another variable).
- Real code, with real leak-fix commits as independent ground truth.
- A test codebase written by someone other than the detector's author.
- How the false-alarm rate scales on a large codebase, where conventions are noisier.
- Why strict's split-half replication rejects a rule that holds 46 of 47 times.

Files: `gen_code.py` (codebase), `src/` (generated), `extract.py` (libclang facts; `HANDED_ON=0` gives v3), `facts_v3.txt`, `facts_v4.txt`, `run_egm.py`.
