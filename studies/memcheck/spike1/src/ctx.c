#include <stdlib.h>
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
