"""Trivial reference engines, scored through the same interface as EGM (interface.py).

They exist so that "better" is measured against what little or no learning achieves, not only against the previous
EGM. Caveat, reported with every profile: they are *given* the world's relation phrases, which EGM must discover
itself, so they have an advantage in segmentation.

  B0 stated:    no inference at all. Retains every stated fact, derives nothing.
  B1 majority:  in each one-value relation (>= 95% of subjects have one value), answers the majority value for
                subjects of the same kind that have no value. "Same kind" = subjects of another relation at least half of
                whose subjects also have a value here. Confidence = the majority value's share.
  B2 inverse:   one-hop inverses and symmetries: if S(b,a) is stated for >= 80% of the R(a,b) whose b has a known value
                in S (>= 5 such cases, >= 3 agreeing), derives S(b,a) for every R(a,b). Confidence = that agreement.
"""
import time
from collections import Counter, defaultdict
from typing import Sequence

from interface import Answer, Fact, Run, parse_fact


def _stated(lines, rels):
    rels = sorted(rels, key=len, reverse=True)
    return {f for f in (parse_fact(l, rels) for l in lines) if f}


class StatedOnly:
    name = "B0-stated"

    def run(self, lines, rels, probes) -> Run:
        t = time.time(); F = _stated(lines, rels)
        return Run([], {p: p in F for p in probes}, set(), time.time() - t, None)


class Majority:
    name = "B1-majority"

    def run(self, lines, rels, probes) -> Run:
        t = time.time(); F = _stated(lines, rels)
        vals = defaultdict(lambda: defaultdict(set))          # rel -> subject -> values
        for r, a, b in F:
            vals[r][a].add(b)
        answers = []
        for R, per in vals.items():
            single = sum(1 for v in per.values() if len(v) == 1)
            if not per or single / len(per) < 0.95:
                continue
            c = Counter(next(iter(v)) for v in per.values() if len(v) == 1)
            v, cnt = c.most_common(1)[0]; share = cnt / single
            have = set(per)
            cands = set()
            for R2, per2 in vals.items():
                if R2 == R:
                    continue
                s2 = set(per2)
                if s2 and len(s2 & have) / len(s2) >= 0.5:
                    cands |= s2 - have
            answers += [Answer((R, x, v), "derived", share) for x in sorted(cands)]
        return Run(answers, {p: p in F for p in probes}, set(), time.time() - t, None)


class Inverse:
    name = "B2-inverse"

    def run(self, lines, rels, probes) -> Run:
        t = time.time(); F = _stated(lines, rels)
        by = defaultdict(set); subj = defaultdict(set)
        for r, a, b in F:
            by[r].add((a, b)); subj[r].add(a)
        best = {}
        for R in by:
            for S in by:
                known = [(a, b) for a, b in by[R] if a != b and b in subj[S]]
                agree = sum(1 for a, b in known if (b, a) in by[S])
                if len(known) >= 5 and agree >= 3 and agree / len(known) >= 0.8:
                    for a, b in by[R]:
                        f = (S, b, a)
                        if a != b and f not in F:
                            best[f] = max(best.get(f, 0.0), agree / len(known))
        answers = [Answer(f, "derived", c, []) for f, c in sorted(best.items())]
        return Run(answers, {p: p in F for p in probes}, set(), time.time() - t, None)


BASELINES = [StatedOnly(), Majority(), Inverse()]
