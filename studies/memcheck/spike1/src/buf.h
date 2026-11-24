#ifndef BUF_H
#define BUF_H
typedef struct buf buf_t;
buf_t *buf_new(int cap);
void buf_release(buf_t *b);
int buf_append(buf_t *b, int v);
int buf_len(buf_t *b);
#endif
