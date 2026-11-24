# memq: ask whether a function leaks

```
python3 memq.py CODE.c -I include/ --ask "report_usage is a ?"
cat code.c | python3 memq.py - -I include/        # paste, then type queries
```

It runs clang's parser over the code, gives the facts to EGM, and EGM learns the code's own resource conventions.
A function is a **memory leak** when one of its handles breaks a learned convention without being handed on. The
answer includes EGM's proof.

On the spike 1 codebase (`spike1/`):

| query | answer |
|---|---|
| `report_usage is a ?` | MEMORY LEAK: `c` from `ctx_create()` ends with `ctx_run()`, but the convention is `ctx_destroy()` |
| a correct user | no leak found: ends with `ctx_destroy()`, consistent with the rest of the code |
| a factory or registry | no leak found: handed on (return or field); the caller owns it |
| a borrower of `ctx_default()` | no leak found: consistent with how the rest of the code uses `ctx_default()` |

**The limit: a single pasted function.**

- A function pasted alone gets "not enough evidence". One use of `ctx_create()` can't teach a convention.
- The same goes for plain `malloc`, which clang's analyzer catches at once.

memq judges a function against the conventions of the code around it, so it needs that code, or conventions
learned beforehand from a corpus. "No leak found" means no learned convention is broken, not that the function is
proven safe.
