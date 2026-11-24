#include "ctx.h"
#include "buf.h"

struct registry { ctx_t *slot; int used; };

int fetch_order(void) {
    ctx_t *c = ctx_create("fetch_order");
    ctx_set(c, "retries", 1);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int push_frame(int n) {
    ctx_t *h = ctx_create("push_frame");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "mode", i); total += ctx_get(h, "mode"); }
    ctx_destroy(h);
    return total;
}

int mark_config(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "level", x);
    ctx_set(b, "level", x * 1);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int wrap_table(void) {
    ctx_t *c = ctx_create("wrap_table");
    ctx_set(c, "retries", 2);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int index_user(int n) {
    ctx_t *h = ctx_create("index_user");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "retries", i); total += ctx_get(h, "retries"); }
    ctx_destroy(h);
    return total;
}

int seal_user(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "level", x);
    ctx_set(b, "level", x * 1);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int seal_token(void) {
    ctx_t *c = ctx_create("seal_token");
    ctx_set(c, "retries", 1);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int render_config(int n) {
    ctx_t *h = ctx_create("render_config");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "level", i); total += ctx_get(h, "level"); }
    ctx_destroy(h);
    return total;
}

int join_order(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "mode", x);
    ctx_set(b, "mode", x * 5);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int pack_order(void) {
    ctx_t *c = ctx_create("pack_order");
    ctx_set(c, "mode", 4);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int trace_user(int n) {
    ctx_t *h = ctx_create("trace_user");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "mode", i); total += ctx_get(h, "mode"); }
    ctx_destroy(h);
    return total;
}

int fold_page(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "retries", x);
    ctx_set(b, "retries", x * 9);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int rank_queue(void) {
    ctx_t *c = ctx_create("rank_queue");
    ctx_set(c, "retries", 8);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int trace_batch(int n) {
    ctx_t *h = ctx_create("trace_batch");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "level", i); total += ctx_get(h, "level"); }
    ctx_destroy(h);
    return total;
}

int seal_batch(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "retries", x);
    ctx_set(b, "retries", x * 6);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int cache_batch(void) {
    ctx_t *c = ctx_create("cache_batch");
    ctx_set(c, "mode", 2);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int tally_table(int n) {
    ctx_t *h = ctx_create("tally_table");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "level", i); total += ctx_get(h, "level"); }
    ctx_destroy(h);
    return total;
}

int spin_event(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "retries", x);
    ctx_set(b, "retries", x * 1);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int seal_queue(void) {
    ctx_t *c = ctx_create("seal_queue");
    ctx_set(c, "size", 6);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int copy_event(int n) {
    ctx_t *h = ctx_create("copy_event");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "retries", i); total += ctx_get(h, "retries"); }
    ctx_destroy(h);
    return total;
}

int wrap_batch(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "retries", x);
    ctx_set(b, "retries", x * 2);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int pull_batch(void) {
    ctx_t *c = ctx_create("pull_batch");
    ctx_set(c, "retries", 5);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int count_queue(int n) {
    ctx_t *h = ctx_create("count_queue");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "mode", i); total += ctx_get(h, "mode"); }
    ctx_destroy(h);
    return total;
}

int probe_order(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "mode", x);
    ctx_set(b, "mode", x * 8);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int pull_page(void) {
    ctx_t *c = ctx_create("pull_page");
    ctx_set(c, "size", 3);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int index_table(int n) {
    ctx_t *h = ctx_create("index_table");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "retries", i); total += ctx_get(h, "retries"); }
    ctx_destroy(h);
    return total;
}

int wrap_order(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "retries", x);
    ctx_set(b, "retries", x * 7);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

int pack_batch(void) {
    ctx_t *c = ctx_create("pack_batch");
    ctx_set(c, "level", 7);
    int r = ctx_run(c);
    ctx_destroy(c);
    return r;
}

int join_queue(int n) {
    ctx_t *h = ctx_create("join_queue");
    if (!h) return -1;
    int total = 0;
    for (int i = 0; i < n; i++) { ctx_set(h, "retries", i); total += ctx_get(h, "retries"); }
    ctx_destroy(h);
    return total;
}

int spin_user(int x) {
    ctx_t *a = ctx_create("a");
    ctx_t *b = ctx_create("b");
    ctx_set(a, "level", x);
    ctx_set(b, "level", x * 3);
    int r = ctx_run(a) - ctx_run(b);
    ctx_destroy(b);
    ctx_destroy(a);
    return r;
}

ctx_t *make_page_ctx0(int v) {
    ctx_t *c = ctx_create("make_page_ctx0");
    ctx_set(c, "level", v);
    return c;
}

ctx_t *make_page_ctx1(int v) {
    ctx_t *c = ctx_create("make_page_ctx1");
    ctx_set(c, "level", v);
    return c;
}

void register_config0(struct registry *reg) {
    ctx_t *c = ctx_create("register_config0");
    ctx_set(c, "mode", 1);
    reg->slot = c;
    reg->used = 1;
}

void register_event1(struct registry *reg) {
    ctx_t *c = ctx_create("register_event1");
    ctx_set(c, "mode", 1);
    reg->slot = c;
    reg->used = 1;
}

int mark_order(int n) {
    buf_t *b = buf_new(n + 1);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int scan_batch(int n) {
    buf_t *b = buf_new(n + 2);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int emit_order(int n) {
    buf_t *b = buf_new(n + 3);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int join_frame(int n) {
    buf_t *b = buf_new(n + 4);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int trace_token(int n) {
    buf_t *b = buf_new(n + 5);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int tune_frame(int n) {
    buf_t *b = buf_new(n + 1);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int fold_config(int n) {
    buf_t *b = buf_new(n + 2);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int flush_frame(int n) {
    buf_t *b = buf_new(n + 3);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int split_table(int n) {
    buf_t *b = buf_new(n + 4);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int lift_event(int n) {
    buf_t *b = buf_new(n + 5);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int split_config(int n) {
    buf_t *b = buf_new(n + 1);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int sync_user(int n) {
    buf_t *b = buf_new(n + 2);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int parse_event(int n) {
    buf_t *b = buf_new(n + 3);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int load_user(int n) {
    buf_t *b = buf_new(n + 4);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int build_token(int n) {
    buf_t *b = buf_new(n + 5);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int pull_user(int n) {
    buf_t *b = buf_new(n + 1);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int emit_token(int n) {
    buf_t *b = buf_new(n + 2);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int spin_frame(int n) {
    buf_t *b = buf_new(n + 3);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int lift_queue(int n) {
    buf_t *b = buf_new(n + 4);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int push_page(int n) {
    buf_t *b = buf_new(n + 5);
    for (int i = 0; i < n; i++) buf_append(b, i);
    int len = buf_len(b);
    buf_release(b);
    return len;
}

int fold_table(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int spin_batch(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int probe_token(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int trace_event(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int drop_user(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int stamp_event(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int audit_event(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int send_user(int x) {
    ctx_t *d = ctx_default();
    ctx_set(d, "mode", x);
    return ctx_run(d);
}

int build_batch(int x) {
    ctx_t *c = ctx_create("build_batch");
    buf_t *b = buf_new(4);
    buf_append(b, x);
    ctx_set(c, "size", buf_len(b));
    int r = ctx_run(c);
    buf_release(b);
    ctx_destroy(c);
    return r;
}

int audit_order(int x) {
    ctx_t *c = ctx_create("audit_order");
    buf_t *b = buf_new(4);
    buf_append(b, x);
    ctx_set(c, "size", buf_len(b));
    int r = ctx_run(c);
    buf_release(b);
    ctx_destroy(c);
    return r;
}

int weigh_config(int x) {
    ctx_t *c = ctx_create("weigh_config");
    buf_t *b = buf_new(4);
    buf_append(b, x);
    ctx_set(c, "size", buf_len(b));
    int r = ctx_run(c);
    buf_release(b);
    ctx_destroy(c);
    return r;
}

int parse_frame(int x) {
    ctx_t *c = ctx_create("parse_frame");
    buf_t *b = buf_new(4);
    buf_append(b, x);
    ctx_set(c, "size", buf_len(b));
    int r = ctx_run(c);
    buf_release(b);
    ctx_destroy(c);
    return r;
}

int trace_order(int x) {
    ctx_t *c = ctx_create("trace_order");
    buf_t *b = buf_new(4);
    buf_append(b, x);
    ctx_set(c, "size", buf_len(b));
    int r = ctx_run(c);
    buf_release(b);
    ctx_destroy(c);
    return r;
}

int sort_config(int x) {
    ctx_t *c = ctx_create("sort_config");
    buf_t *b = buf_new(4);
    buf_append(b, x);
    ctx_set(c, "size", buf_len(b));
    int r = ctx_run(c);
    buf_release(b);
    ctx_destroy(c);
    return r;
}

int report_usage(int x) {
    ctx_t *c = ctx_create("report");
    ctx_set(c, "level", x);
    int r = ctx_run(c);
    return r;
}
