"""C10 / Round 1 C-H5: counterfactual proof faithfulness, independent of the engine's bookkeeping.

For a sampled derived fact F with proof P: collect P's stated leaves (premises that are stated facts; a derived
premise is followed down to its own stated leaves), remove those observation lines, rerun the same engine under the
same policy, and ask F's question again.

  removed       F is no longer derived: the proof was what produced it                              (faithful)
  alternative   F is derived again, by a proof none of whose premises depends on what was removed:
                every premise is stated in the reduced evidence, or derived again there               (faithful)
  FAIL          F is derived again, but its proof is missing or cites a removed fact that is neither
                stated nor derived in the reduced evidence: the proof did not explain the answer

Engines are reached through the evaluation interface plus one optional adapter method (added after the freeze):
``adapter.ask(lines, rels, subject, relation) -> list[Answer]`` for one question, under the adapter's policy.
"""
import random

from interface import parse_fact


def leaves(fact, stated, derived, seen=None):
    """Stated leaves of a fact's proof tree; None if a premise is neither stated nor derived (a broken proof)."""
    seen = set() if seen is None else seen
    if fact in seen:
        return set()
    seen.add(fact)
    a = derived.get(fact)
    if a is None or not a.proof:
        return None
    out = set()
    for p in a.proof:
        if p in stated:
            out.add(p)
        elif p in derived:
            sub = leaves(p, stated, derived, seen)
            if sub is None:
                return None
            out |= sub
        else:
            return None
    return out


def check(adapter, lines, rels, run, n=20, seed=0):
    """Counterfactual outcomes for up to n derived facts of `run` (sampled with `seed`)."""
    rels = sorted(rels, key=len, reverse=True)
    stated = {f for f in (parse_fact(l, rels) for l in lines) if f}
    derived = {a.fact: a for a in run.answers if a.status == "derived" and a.fact not in stated}
    pool = sorted(derived)
    random.Random(seed).shuffle(pool)
    out = []
    for f in pool:
        if len(out) >= n:
            break
        lv = leaves(f, stated, derived)
        if lv is None:
            out.append({"fact": f, "outcome": "FAIL", "why": "the proof cites a premise that is neither stated nor derived"})
            continue
        if not lv:
            continue
        reduced = [l for l in lines if parse_fact(l, rels) not in lv]
        rstated = stated - lv
        got = [a for a in adapter.ask(reduced, rels, f[1], f[0]) if a.status == "derived" and a.fact == f]
        if not got:
            out.append({"fact": f, "outcome": "removed", "leaves": len(lv)})
            continue
        a = got[0]
        if not a.proof:
            out.append({"fact": f, "outcome": "FAIL", "why": "derived again with no proof", "leaves": len(lv)})
            continue
        bad = []
        for p in a.proof:
            if p in rstated:
                continue
            again = [x for x in adapter.ask(reduced, rels, p[1], p[0]) if x.status == "derived" and x.fact == p]
            if not again:
                bad.append(p)
        if bad:
            out.append({"fact": f, "outcome": "FAIL", "why": f"derived again citing {bad[0]}, which the reduced evidence no longer holds",
                        "leaves": len(lv)})
        else:
            out.append({"fact": f, "outcome": "alternative", "leaves": len(lv)})
    return out


def summarize(results):
    c = {"removed": 0, "alternative": 0, "FAIL": 0}
    for r in results:
        c[r["outcome"]] += 1
    c["checked"] = len(results)
    c["faithful"] = (c["removed"] + c["alternative"]) / len(results) if results else None
    return c
