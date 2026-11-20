"""E8: two-part code length (MDL) on the training corpus: xz vs word trigram vs discovered-class model.
Prequential (online, adaptive) coding: each word is coded with a model trained only on the preceding sentences,
so model cost is paid implicitly -- this is what an adaptive arithmetic coder would actually achieve (+ ~2 bytes)."""
import math, lzma, json, exp2_counters as E
train = E.train
words = sum(len(s) for s in train)
raw = "\n".join(" ".join(s) for s in train).encode()
def preq(make, chunk=100):
    bits = 0.0
    for k in range(0, len(train), chunk):
        past = train[:k]
        if k == 0:
            bits += sum(len(s) for s in train[:chunk]) * math.log2(len(E.vocab)); continue
        m = make(past); bits += m.bits(train[k:k+chunk]) * sum(len(s) for s in train[k:k+chunk])
    return bits
vocab = E.vocab
def mk_ngram(p): return E.NGram(3, p, vocab)
def mk_class(p):
    c = E.discover_classes(p)
    for w in vocab: c.setdefault(w, w)
    return E.ClassModel(p, c)
# true entropy of the generator per word (templates uniform, words uniform within category)
R = {"words": words, "raw_bytes": len(raw), "xz_bytes": len(lzma.compress(raw, preset=9)),
     "trigram_prequential_bytes": int(preq(mk_ngram) / 8), "class_prequential_bytes": int(preq(mk_class) / 8),
     "voltex_vtxe_bytes": 444381}
print(json.dumps(R, indent=1)); json.dump(R, open("results_e8.json", "w"), indent=1)
