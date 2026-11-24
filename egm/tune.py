"""Tune engine settings to one dataset, from the dataset itself (studies/noise).

The engine's mechanisms stay the same; tuning only picks values for existing settings. It hides some of the stated
facts, asks which settings recover them best, and adopts a change only when it helps in every fold. So a setting
changes only when the data clearly supports the change.

    import egm
    result = egm.tune("facts.txt")
    print(result.report())
    with egm.open("facts.txt", settings=result.settings) as e: ...

Optional ``labels``: facts you have verified (from outside the dataset). Then the score is measured on them instead
of on hidden stated facts.

Optional ``settings``: a base configuration every candidate starts from (for example a sized MAXWORDS). Optional
``expanded=True``: also search TENDENCYSTEPS, DEPTH 1 and 2, and MAXWORDS sized to the data's vocabulary
(``expanded_space``). It found the hand-chosen configuration on the Python standard library (studies/strengths) at
about 2.6x the cost, so it is opt-in. What tuning finds fits this dataset; validate on yours before relying on it.
"""
import os
import random
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .engine import Engine

#: (setting, values to try). The first value is the engine default.
DEFAULT_SPACE: List[Tuple[str, list]] = [
    ("RATE", [0.4, 0.3, 0.5]), ("LIFT", [5, 3, 8]), ("SUPPORT", [3, 2, 5]), ("PCA", [0.8, 0.7, 0.9]),
    ("COVERAGE", [1, 0]), ("CORROBORATE", [1, 0]), ("DEPTH", [4, 0]), ("CHAIN", [2, 3]), ("CONDITIONS", [1, 0]),
    ("TREES", [0, 1]), ("REPLICATE", [0, 1]), ("QUARANTINE", [0, 1]), ("VOTE", [0, 1]),
]
Fact3 = Tuple[str, str, str]


def expanded_space(facts: str) -> List[Tuple[str, list]]:
    """DEFAULT_SPACE plus the settings that decided the code studies (studies/strengths): TENDENCYSTEPS (-1, 0),
    DEPTH 1 and 2, and MAXWORDS sized from the data (distinct words + 1,000) when the vocabulary exceeds the default
    cap. Every value is either an engine default or derived from ``facts``; nothing is domain-specific."""
    with open(facts) as fh:
        words = len({w for l in fh for w in l.split()})
    space: List[Tuple[str, list]] = []
    if words + 1000 > 12000:
        space.append(("MAXWORDS", [12000, words + 1000]))
    space.append(("TENDENCYSTEPS", [-1, 0]))
    space += [(k, [4, 0, 1, 2]) if k == "DEPTH" else (k, list(v)) for k, v in DEFAULT_SPACE]
    return space


@dataclass
class TuneResult:
    settings: Dict[str, object]          # only the settings that changed from the defaults
    baseline: float                      # objective with the defaults
    tuned: float                         # objective with ``settings``
    baseline_folds: List[float]
    tuned_folds: List[float]
    history: List[dict] = field(default_factory=list)   # every value tried: setting, value, score, folds, adopted
    evaluations: int = 0
    mode: str = "holdout"
    base: Dict[str, object] = field(default_factory=dict)   # the ``settings`` every candidate started from

    @property
    def all_settings(self) -> Dict[str, object]:
        """The base settings plus the changes: what to pass to egm.open or egm build."""
        return dict(self.base, **self.settings)

    def report(self) -> str:
        start = "the base settings" if self.base else "defaults"
        lines = [f"tuning by {self.mode}: F0.5 {self.baseline:.4f} with {start} -> {self.tuned:.4f} tuned ({self.evaluations} evaluations)"]
        for k, v in self.base.items():
            lines.append(f"  base: SET {k} {v}")
        if not self.settings:
            lines.append("no change is clearly supported by this data: keep the defaults")
        for k, v in self.settings.items():
            lines.append(f"  SET {k} {v}")
        return "\n".join(lines)


def _f(p: float, r: float, beta: float = 0.5) -> float:
    b2 = beta * beta
    return (1 + b2) * p * r / (b2 * p + r) if p + r > 0 else 0.0


def _split(line: str, rels: Sequence[str]) -> Optional[Fact3]:
    for rel in rels:
        k = f" {rel} "
        if k in line:
            a, b = line.split(k, 1)
            return (rel, a.strip(), b.strip())
    return None


def _derived(lines: Iterable[str], settings: dict, binary: Optional[str]) -> List[Fact3]:
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "facts.txt")
        with open(p, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        with Engine(facts=[p], settings=settings, binary=binary) as e:
            return [(f.relation, f.subject, f.object) for f in e.infer_all()]


def score(derived: Iterable[Fact3], answers: Iterable[Fact3], pairs=None) -> Tuple[float, float, float]:
    """F0.5, precision, recall of derived facts against known answers. Precision counts only derived facts whose
    (relation, subject) has a known answer (or is in ``pairs``, where the answers are known to be complete): the only
    place where right and wrong can be told apart."""
    ans = set(answers); pairs = set(pairs) if pairs is not None else {(r, a) for r, a, _ in ans}
    judged = [f for f in set(derived) if (f[0], f[1]) in pairs]
    ok = sum(1 for f in judged if f in ans)
    p = ok / len(judged) if judged else 1.0
    r = ok / len(ans) if ans else 0.0
    return _f(p, r), p, r


def tune(facts: str, folds: int = 3, holdout: float = 0.15, space: Optional[List[Tuple[str, list]]] = None,
         min_gain: float = 0.005, sweeps: int = 2, seed: int = 0, labels: Optional[Iterable[str]] = None,
         label_pairs: Optional[Iterable[Tuple[str, str]]] = None, min_relation_facts: int = 20, binary: Optional[str] = None,

         progress: Optional[Callable[[str], None]] = None, settings: Optional[Dict[str, object]] = None,
         expanded: bool = False) -> TuneResult:
    """Pick settings for the facts file ``facts``.

    Without ``labels`` (self-tuning): ``folds`` disjoint samples of ``holdout`` of the stated facts are hidden in turn,
    and the score is how well each candidate setting recovers them (F0.5). With ``labels`` (facts verified outside the
    dataset): the engine sees all of ``facts``, and the score is measured on the labels. ``label_pairs`` optionally
    lists the (relation, subject) pairs whose answers the labels give completely, so a wrong answer there counts.

    Coordinate descent over ``space`` (default ``DEFAULT_SPACE``; ``expanded=True`` uses ``expanded_space(facts)``),
    at most ``sweeps`` passes. A value is adopted only if it raises the mean score by at least ``min_gain`` and raises
    it in every fold. ``settings`` is the base configuration; the result's ``settings`` lists only changes from it.
    """
    if space is not None and expanded:
        raise ValueError("pass either space or expanded=True, not both")
    space = space or (expanded_space(facts) if expanded else DEFAULT_SPACE)
    base = dict(settings or {})
    say = progress or (lambda s: None)
    with open(facts) as fh:
        lines = [l.rstrip("\n") for l in fh if l.strip()]
    with Engine(facts=[facts], settings=base, binary=binary) as e:
        rels = sorted({r.relation for r in e.relations()}, key=len, reverse=True)
    if labels is not None:
        answers = [f for f in (_split(l, rels) for l in labels) if f]
        if not answers:
            raise ValueError("none of the labels matches a relation the engine learned from the facts")
        tasks = [(lines, answers, set(map(tuple, label_pairs)) if label_pairs is not None else None)]
        mode = "labels"
    else:
        uniq = sorted({f for f in (_split(l, rels) for l in lines) if f})
        per = {}
        for f in uniq: per.setdefault(f[0], []).append(f)
        cand = [f for r in sorted(per) if len(per[r]) >= min_relation_facts for f in per[r]]
        random.Random(seed).shuffle(cand)
        k = int(holdout * len(cand))
        if k < 10 or folds * k > len(cand):
            raise ValueError(f"too few facts to tune: {len(cand)} facts in relations with >= {min_relation_facts} facts")
        tasks = []
        for i in range(folds):
            hidden = set(cand[i * k:(i + 1) * k])
            keep = [l for l in lines if _split(l, rels) not in hidden]
            tasks.append((keep, sorted(hidden), None))
        mode = f"holdout ({folds} folds x {holdout:.0%})"
    evals = 0
    cache: Dict[tuple, list] = {}

    def derive(cfg):   # derived facts per task, cached per setting
        nonlocal evals
        key = tuple(sorted(cfg.items()))
        if key not in cache:
            cache[key] = []
            for keep, _, _ in tasks:
                evals += 1
                cache[key].append(set(_derived(keep, dict(base, **cfg), binary)))
        return cache[key]

    def run(cfg):   # score per task
        return [score(dd, ans, pairs)[0] for dd, (_, ans, pairs) in zip(derive(cfg), tasks)]
    cur: Dict[str, object] = {}
    cur_f = run(cur); base_f = list(cur_f)
    mean = lambda xs: sum(xs) / len(xs)
    say(f"defaults: {mean(cur_f):.4f}")
    history = []
    for sweep in range(sweeps):
        changed = False
        for name, values in space:
            best = None
            start = base.get(name, values[0])   # the value in force before tuning touches this setting
            now = cur.get(name, start)
            for v in values:
                if v == now: continue
                cfg = dict(cur); cfg[name] = v
                if v == start: cfg.pop(name)
                fs = run(cfg)
                gain = mean(fs) - mean(cur_f)
                ok = gain >= min_gain and all(a > b for a, b in zip(fs, cur_f))
                history.append({"sweep": sweep + 1, "setting": name, "value": v, "score": mean(fs), "folds": fs, "clear_gain": ok})
                say(f"  {name}={v}: {mean(fs):.4f} ({'+' if gain >= 0 else ''}{gain:.4f}){' clear gain' if ok else ''}")
                if ok and (best is None or mean(fs) > mean(best[1])):
                    best = (v, fs, cfg)
            if best:
                cur = best[2]; cur_f = run(cur); changed = True
                history.append({"sweep": sweep + 1, "setting": name, "value": best[0], "score": mean(cur_f), "folds": cur_f, "adopted": True})
                say(f"adopt {name}={best[0]}: {mean(cur_f):.4f}")
        if not changed:
            break
    return TuneResult(settings=cur, baseline=mean(base_f), tuned=mean(cur_f), baseline_folds=base_f, tuned_folds=cur_f,
                      history=history, evaluations=evals, mode=mode, base=base)
