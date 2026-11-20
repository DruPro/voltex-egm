"""Question sets, the scripted EGM solver, and scoring.

Question kinds (each answerable from the five code relations):
  lookup          one value   X is defined in ?
  callers         list        ? calls X
  caller_modules  list        modules of (? calls X)
  raises_1hop     list        X raises ?  plus  (X calls ?) raises ?
  grandparent     list        (X inherits from ?) inherits from ?
  imports         list        X imports ?
"""
import collections
import json
import random
import re

KINDS = ["lookup", "callers", "caller_modules", "raises_1hop", "grandparent", "imports"]
DEFAULT_COUNTS = {"lookup": 8, "callers": 8, "caller_modules": 4, "raises_1hop": 6, "grandparent": 5, "imports": 5}


# --- question generation (from extractor truth, never from the knowledge base) -------------
def make_questions(truth, seed=2026, counts=None):
    counts = dict(DEFAULT_COUNTS, **(counts or {}))
    rng = random.Random(seed)
    T = {r: set(map(tuple, v)) for r, v in truth.items()}
    defined = dict(T["is defined in"])
    callers, callees, rz, bases, imp = (collections.defaultdict(set) for _ in range(5))
    for a, b in T["calls"]: callers[b].add(a); callees[a].add(b)
    for a, e in T["raises"]: rz[a].add(e)
    for c, b in T["inherits from"]: bases[c].add(b)
    for a, b in T["imports"]: imp[a].add(b)
    Q = []

    def add(kind, text, ans, fmt):
        Q.append({"id": f"q{len(Q) + 1}", "kind": kind, "question": text, "answer_format": fmt, "truth": ans})

    def pick(pool, n):
        pool = sorted(pool)
        return rng.sample(pool, min(n, len(pool)))

    for n in pick([n for n in defined if not n.split("__")[-1].startswith("_")], counts["lookup"]):
        add("lookup", f"In which module is `{n}` defined?", defined[n], "one module name")
    tgts = [b for b in callers if 2 <= len(callers[b]) <= 7]
    for b in pick(tgts, counts["callers"]):
        add("callers", f"List every function or method that calls `{b}` directly.", sorted(callers[b]), "a list of names")
    for b in pick([x for x in tgts if len({defined.get(c) for c in callers[x]}) >= 2], counts["caller_modules"]):
        add("caller_modules", f"Which modules contain code that calls `{b}` directly?",
            sorted({defined[c] for c in callers[b] if c in defined}), "a list of module names")
    for a in pick([a for a in callees if any(rz[c] - rz[a] for c in callees[a])], counts["raises_1hop"]):
        add("raises_1hop", f"Which exception types can `{a}` raise, itself or through functions it calls directly?",
            sorted(rz[a] | set().union(*[rz[c] for c in callees[a]])), "a list of exception names")
    for c in pick([c for c in bases if any(b in bases for b in bases[c])], counts["grandparent"]):
        add("grandparent", f"What are the grandparent classes of `{c}`?",
            sorted(set().union(*[bases[b] for b in bases[c] if b in bases])), "a list of class names")
    for m in pick(imp, counts["imports"]):
        add("imports", f"Which modules does module `{m}` import directly?", sorted(imp[m]), "a list of module names")
    return Q


def public(questions):
    return [{k: q[k] for k in ("id", "kind", "question", "answer_format")} for q in questions]


# --- the scripted solver: fixed EGM queries per kind, no LLM ------------------------------
def target(q):
    found = re.findall(r"`([^`]+)`", q["question"])
    if not found:
        raise ValueError(f"{q['id']}: no `name` in question")
    return found[0]


def solve(engine, questions, strict=False):
    def objs(p): return engine.values(p, strict=strict)      # pattern ends in ?: objects
    def subs(p): return engine.values(p, strict=strict)      # pattern starts with ?: subjects
    out = []
    for q in questions:
        x, k = target(q), q["kind"]
        if k == "lookup":
            a = objs(f"{x} is defined in ?")
            a = a[0] if len(a) == 1 else a
        elif k == "callers":
            a = subs(f"? calls {x}")
        elif k == "caller_modules":
            a = sorted({m for c in subs(f"? calls {x}") for m in objs(f"{c} is defined in ?")})
        elif k == "raises_1hop":
            a = sorted(set(objs(f"{x} raises ?")) | {e for c in objs(f"{x} calls ?") for e in objs(f"{c} raises ?")})
        elif k == "grandparent":
            a = sorted({g for b in objs(f"{x} inherits from ?") for g in objs(f"{b} inherits from ?")})
        elif k == "imports":
            a = objs(f"{x} imports ?")
        else:
            raise ValueError(f"unknown kind {k}")
        out.append({"id": q["id"], "answer": a})
    return out


# --- scoring (exact for one value, F1 for lists) -------------------------------------------
def _nm(s):
    return re.sub(r"[`'\"\s]", "", str(s)).replace(".py", "").strip().lower()


def _as_list(a):
    if isinstance(a, list):
        return [_nm(x) for x in a if _nm(x)]
    return [_nm(x) for x in re.split(r"[,;\n]| and ", str(a)) if _nm(x)]


def grade(q, ans):
    truth = q["truth"]
    if isinstance(truth, str):
        vals = _as_list(ans)
        ok = len(vals) == 1 and vals[0] == _nm(truth)
        return {"exact": ok, "f1": 1.0 if ok else 0.0}
    T = {_nm(x) for x in truth}; A = set(_as_list(ans))
    tp = len(T & A); p = tp / len(A) if A else 0.0; r = tp / len(T) if T else 0.0
    return {"exact": A == T, "f1": 0.0 if tp == 0 else 2 * p * r / (p + r)}


def score(key, answers):
    amap = {a["id"]: a["answer"] for a in answers}
    rows, by = [], collections.defaultdict(list)
    for q in key:
        g = grade(q, amap.get(q["id"], []))
        rows.append({"id": q["id"], "kind": q["kind"], **g, "missing": q["id"] not in amap})
        by[q["kind"]].append(g)
    n = len(rows)
    return {
        "questions": n,
        "mean_f1": round(sum(r["f1"] for r in rows) / n, 3) if n else None,
        "exact": sum(r["exact"] for r in rows),
        "missing": sum(r["missing"] for r in rows),
        "by_kind": {k: {"n": len(v), "mean_f1": round(sum(x["f1"] for x in v) / len(v), 3),
                        "exact": sum(x["exact"] for x in v)} for k, v in by.items()},
        "rows": rows,
    }
