#ifndef CTX_H
#define CTX_H
typedef struct ctx ctx_t;
ctx_t *ctx_create(const char *name);
void ctx_destroy(ctx_t *c);
int ctx_set(ctx_t *c, const char *key, int value);
int ctx_get(ctx_t *c, const char *key);
int ctx_run(ctx_t *c);
ctx_t *ctx_default(void);   /* shared, owned by the library: never destroy */
#endif
