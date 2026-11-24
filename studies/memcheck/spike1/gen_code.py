"""Spike 1 test codebase: an opaque handle library (ctx_*, in its own file) and an app that uses it.
Exactly one function leaks (report_usage). Some functions transfer ownership (return or store the handle):
those must NOT be flagged. Written by hand-picked templates; the answer is known to the author (spike, not a test)."""
import random, os
r = random.Random(7)
os.makedirs("src", exist_ok=True)
open("src/ctx.h", "w").write("""#ifndef CTX_H
#define CTX_H
typedef struct ctx ctx_t;
ctx_t *ctx_create(const char *name);
void ctx_destroy(ctx_t *c);
int ctx_set(ctx_t *c, const char *key, int value);
int ctx_get(ctx_t *c, const char *key);
int ctx_run(ctx_t *c);
ctx_t *ctx_default(void);   /* shared, owned by the library: never destroy */
#endif
""")
open("src/ctx.c", "w").write("""#include <stdlib.h>
#include <string.h>
#include "ctx.h"
struct ctx { char name[32]; int vals[8]; };
ctx_t *ctx_create(const char *name) { ctx_t *c = malloc(sizeof *c); if (c) { strncpy(c->name, name, 31); c->name[31] = 0; memset(c->vals, 0, sizeof c->vals); } return c; }
void ctx_destroy(ctx_t *c) { free(c); }
int ctx_set(ctx_t *c, const char *key, int value) { c->vals[(unsigned char)key[0] % 8] = value; return 0; }
int ctx_get(ctx_t *c, const char *key) { return c->vals[(unsigned char)key[0] % 8]; }
int ctx_run(ctx_t *c) { return c->vals[0] + c->vals[1]; }
static struct ctx shared;
ctx_t *ctx_default(void) { return &shared; }
""")
open("src/buf.h", "w").write("""#ifndef BUF_H
#define BUF_H
typedef struct buf buf_t;
buf_t *buf_new(int cap);
void buf_release(buf_t *b);
int buf_append(buf_t *b, int v);
int buf_len(buf_t *b);
#endif
""")
open("src/buf.c", "w").write("""#include <stdlib.h>
#include "buf.h"
struct buf { int n, cap; int *v; };
buf_t *buf_new(int cap) { buf_t *b = malloc(sizeof *b); if (b) { b->n = 0; b->cap = cap; b->v = malloc(sizeof(int) * cap); } return b; }
void buf_release(buf_t *b) { if (b) { free(b->v); free(b); } }
int buf_append(buf_t *b, int v) { if (b->n < b->cap) b->v[b->n++] = v; return b->n; }
int buf_len(buf_t *b) { return b->n; }
""")
verbs = ["emit", "grow", "scale", "pull", "push", "wrap", "lift", "drop", "tune", "spin", "load", "save", "sync", "parse", "render", "index", "scan", "merge", "check", "send", "fetch", "build",
         "probe", "trace", "count", "split", "join", "rank", "cache", "flush", "audit", "stamp", "tally", "weigh",
         "sort", "pack", "seal", "mark", "copy", "fold"]
nouns = ["config", "user", "order", "page", "batch", "queue", "table", "event", "frame", "token"]
fns, used = [], set()
def name():
    while True:
        n = f"{r.choice(verbs)}_{r.choice(nouns)}"
        if n not in used: used.add(n); return n
body = []
# 30 correct users: acquire, use, destroy (varied shapes: early return with cleanup, loops, two handles)
for i in range(30):
    n = name(); k = r.choice(["mode", "level", "size", "retries"]); v = r.randint(1, 9)
    shape = i % 3
    if shape == 0:
        body.append(f"int {n}(void) {{\n    ctx_t *c = ctx_create(\"{n}\");\n    ctx_set(c, \"{k}\", {v});\n    int r = ctx_run(c);\n    ctx_destroy(c);\n    return r;\n}}\n")
    elif shape == 1:
        body.append(f"int {n}(int n) {{\n    ctx_t *h = ctx_create(\"{n}\");\n    if (!h) return -1;\n    int total = 0;\n    for (int i = 0; i < n; i++) {{ ctx_set(h, \"{k}\", i); total += ctx_get(h, \"{k}\"); }}\n    ctx_destroy(h);\n    return total;\n}}\n")
    else:
        body.append(f"int {n}(int x) {{\n    ctx_t *a = ctx_create(\"a\");\n    ctx_t *b = ctx_create(\"b\");\n    ctx_set(a, \"{k}\", x);\n    ctx_set(b, \"{k}\", x * {v});\n    int r = ctx_run(a) - ctx_run(b);\n    ctx_destroy(b);\n    ctx_destroy(a);\n    return r;\n}}\n")
# 4 ownership transfers (must not be flagged): factory returns the handle; registry stores it in a struct field
for i in range(2):
    n = "make_" + r.choice(nouns) + f"_ctx{i}"
    body.append(f"ctx_t *{n}(int v) {{\n    ctx_t *c = ctx_create(\"{n}\");\n    ctx_set(c, \"level\", v);\n    return c;\n}}\n")
body.insert(0, "struct registry { ctx_t *slot; int used; };\n")
for i in range(2):
    n = f"register_{r.choice(nouns)}{i}"
    body.append(f"void {n}(struct registry *reg) {{\n    ctx_t *c = ctx_create(\"{n}\");\n    ctx_set(c, \"mode\", 1);\n    reg->slot = c;\n    reg->used = 1;\n}}\n")
# 20 correct buf users, 8 correct borrowers of the shared ctx (no destroy: correct), 6 using both APIs
for i in range(20):
    n = name()
    body.append(f"int {n}(int n) {{\n    buf_t *b = buf_new(n + {i % 5 + 1});\n    for (int i = 0; i < n; i++) buf_append(b, i);\n    int len = buf_len(b);\n    buf_release(b);\n    return len;\n}}\n")
for i in range(8):
    n = name()
    body.append(f"int {n}(int x) {{\n    ctx_t *d = ctx_default();\n    ctx_set(d, \"mode\", x);\n    return ctx_run(d);\n}}\n")
for i in range(6):
    n = name()
    body.append(f"int {n}(int x) {{\n    ctx_t *c = ctx_create(\"{n}\");\n    buf_t *b = buf_new(4);\n    buf_append(b, x);\n    ctx_set(c, \"size\", buf_len(b));\n    int r = ctx_run(c);\n    buf_release(b);\n    ctx_destroy(c);\n    return r;\n}}\n")
# the one leak: acquires, uses, never releases, doesn't hand it on
body.append("int report_usage(int x) {\n    ctx_t *c = ctx_create(\"report\");\n    ctx_set(c, \"level\", x);\n    int r = ctx_run(c);\n    return r;\n}\n")
r.shuffle(body[1:])
open("src/app.c", "w").write('#include "ctx.h"\n#include "buf.h"\n\n' + "\n".join(body))
print(len(body) - 1, "functions")
