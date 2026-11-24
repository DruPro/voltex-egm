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

| Tool | How it was run | Leak found | False alarms |
|---|---|---|---|
| `gcc -Wall -Wextra` | normal build | no | 0 |
| clang static analyzer (`clang --analyze`) | normal, per file | **no** | 0 |
| gcc `-fanalyzer` | normal, per file | no | 0 |
| clang static analyzer | library and app merged into one file (it can see the `malloc`) | **yes** | 0 |
| gcc `-fanalyzer` | merged into one file | no | 2 (uninitialized value; looks spurious) |
| EGM, `TREES 1` | facts from clang's parser | **yes** | 4, all ownership transfers |
| EGM + one universal rule (a returned or stored pointer has been handed on) | same | **yes** | **0** |

What EGM learned, with nothing telling it which function is a destructor:

- **`buf`:** handles from `buf_new` end with `buf_release`: 26 of 26, a law.
- **`ctx`:** handles from `ctx_create` end with `ctx_destroy`: 46 of 50, a tendency. The 4 exceptions are the
  factories and registries.
- **Borrowed handles:** none of the 8 `ctx_default` handles was flagged, because the rule is anchored on where the
  handle comes from, not on its type.

The report is a conflict with a proof:

```
stated: report_usage__c ends with ctx_run | inferred: report_usage__c ends with ctx_destroy
because report_usage__c comes from ctx_create + ctx_create is source of register_event1__c  [rule: TREE ...]
```

## What it took, and what it says

1. **The data design mattered more than the engine.** The first encoding learned nothing. Two problems had to be
   fixed:
   - EGM folds a relation whose object never varies into the relation's phrasing (every handle came from
     `ctx_create`), so the codebase needed more than one API.
   - Tree rules only conclude one-value relations, so a release has to be stated as `h ends with <last call>`, not
     as one of many `is passed to` facts.

   Both are extractor choices. No engine change was needed.
2. **The division of labour is right:**
   - *Universal semantics*, such as ownership transfer by return or store, belongs in the deterministic layer, as
     in any analyzer.
   - *Project conventions*, such as which function releases which handle and which handles are borrowed, are what
     EGM learned. The analyzer can't learn those, and it can't see them through an opaque library.
3. **Is it better than a static analyzer? On this pattern: complementary, not better.**
   - When the allocation is invisible (normal builds against a library), EGM finds the leak and the analyzers don't.
   - When the analyzer can see the allocation, it finds the leak exactly, with no learning and no false alarms.
   - EGM's rule was a 0.92 tendency, so strict wouldn't admit it, and the leak was found through default inference.

## Not tested yet

- Leaks on one path only (released on the normal path, leaked on an early error return): needs per-exit facts.
- Aliasing (the handle copied to another variable).
- Real code, with real leak-fix commits as independent ground truth.
- A test codebase written by someone other than the detector's author.
- How the false-alarm rate scales on a large codebase, where conventions are noisier.

Files: `gen_code.py` (codebase), `src/` (generated), `extract.py` (libclang facts), `facts.txt`, `run_egm.py`.
