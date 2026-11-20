"""Scoring: extraction quality vs truth, and answers (exact for one value, F1 for lists)."""
import json, re, sys
def nm(s): return re.sub(r"[`'\"\s]", "", str(s)).replace(".py", "").strip().lower()
def facts_of(path):
    out = {r: set() for r in ["defined in", "calls", "raises", "inherits from", "imports"]}
    pat = {"defined in": "is defined in"}
    for l in open(path):
        l = l.strip().strip("-* ").strip()
        for r in sorted(out, key=len, reverse=True):
            parts = l.split(f" {pat.get(r, r)} ")
            if len(parts) == 2 and " " not in parts[0].strip() and " " not in parts[1].strip():
                out[r].add((nm(parts[0]), nm(parts[1]))); break
    return out
def extraction(truth, facts):
    rows = {}
    for r in facts:
        T = {(nm(a), nm(b)) for a, b in truth[r]}; F = facts[r]
        tp = len(T & F); rows[r] = {"truth": len(T), "extracted": len(F), "correct": tp,
                                    "precision": round(tp / len(F), 3) if F else None, "recall": round(tp / len(T), 3) if T else None}
    return rows
def as_list(a):
    if isinstance(a, list): return [nm(x) for x in a if nm(x)]
    return [nm(x) for x in re.split(r"[,;\n]| and ", str(a)) if nm(x)]
def grade(q, ans):
    truth = q["truth"]
    if isinstance(truth, str):
        vals = as_list(ans); ok = len(vals) == 1 and vals[0] == nm(truth)
        return {"exact": ok, "f1": 1.0 if ok else 0.0}
    T = {nm(x) for x in truth}; A = set(as_list(ans))
    tp = len(T & A); p = tp / len(A) if A else 0.0; r = tp / len(T) if T else 0.0
    return {"exact": A == T, "f1": 0.0 if tp == 0 else 2 * p * r / (p + r)}
