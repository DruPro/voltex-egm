#include <stdlib.h>
#include "buf.h"
struct buf { int n, cap; int *v; };
buf_t *buf_new(int cap) { buf_t *b = malloc(sizeof *b); if (b) { b->n = 0; b->cap = cap; b->v = malloc(sizeof(int) * cap); } return b; }
void buf_release(buf_t *b) { if (b) { free(b->v); free(b); } }
int buf_append(buf_t *b, int v) { if (b->n < b->cap) b->v[b->n++] = v; return b->n; }
int buf_len(buf_t *b) { return b->n; }
