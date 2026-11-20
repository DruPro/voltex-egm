"""Questions and hidden key from the static truth. Fixed seed; generated before any agent runs."""
import json, random, collections, sys
t = json.load(open(sys.argv[1])); rng = random.Random(2026)
defined = dict(map(tuple, t["defined in"])); calls = set(map(tuple, t["calls"])); raises = set(map(tuple, t["raises"]))
inh = set(map(tuple, t["inherits from"])); imports = set(map(tuple, t["imports"]))
callers = collections.defaultdict(set); callees = collections.defaultdict(set); rz = collections.defaultdict(set); bases = collections.defaultdict(set); imp = collections.defaultdict(set)
for a, b in calls: callers[b].add(a); callees[a].add(b)
for a, e in raises: rz[a].add(e)
for c, b in inh: bases[c].add(b)
for a, b in imports: imp[a].add(b)
Q = []
def add(kind, text, truth, fmt): Q.append({"id": f"q{len(Q) + 1}", "kind": kind, "question": text, "answer_format": fmt, "truth": truth})
names = sorted(n for n in defined if not n.startswith("_"))
for n in rng.sample(names, 8):
    add("lookup", f"In which module (file name without .py) is `{n}` defined?", defined[n], "one module name")
tgts = sorted(b for b in callers if 2 <= len(callers[b]) <= 7)
for b in rng.sample(tgts, 8):
    add("callers", f"We are changing the signature of `{b}`. List every function or method in the package that calls `{b}` directly.", sorted(callers[b]), "a list of function/method names")
for b in rng.sample([x for x in tgts if len({defined.get(c) for c in callers[x]}) >= 2], 4):
    add("caller_modules", f"If `{b}` changes, which modules (file names without .py) contain code that calls it directly?", sorted({defined[c] for c in callers[b] if c in defined}), "a list of module names")
cands = sorted(a for a in callees if any(rz[c] - rz[a] for c in callees[a]))
for a in rng.sample(cands, 6):
    add("raises_1hop", f"Which exception types can `{a}` raise, either with its own raise statements or through package functions/methods it calls directly?",
        sorted(rz[a] | set().union(*[rz[c] for c in callees[a]])), "a list of exception class names")
gp = sorted(c for c in bases if any(b in bases for b in bases[c]))
for c in rng.sample(gp, min(5, len(gp))):
    add("grandparent", f"What are the base classes of the base classes of `{c}` (its grandparent classes)?", sorted(set().union(*[bases[b] for b in bases[c] if b in bases])), "a list of class names")
for m in rng.sample(sorted(imp), 5):
    add("imports", f"Which other modules of the package does module `{m}` import (file names without .py)?", sorted(imp[m]), "a list of module names")
json.dump([{k: q[k] for k in ("id", "kind", "question", "answer_format")} for q in Q], open(sys.argv[2], "w"), indent=1)
json.dump(Q, open(sys.argv[3], "w"), indent=1)
print(collections.Counter(q["kind"] for q in Q), len(Q))
