"""The evaluation interface: how the capability suite talks to an engine.

The suite scores *behaviour*, never internals. An engine under test is anything that can:
  1. ingest observation lines;
  2. return its answers, each a fact (relation, subject, object) with a status (stated | derived), a confidence in
     [0, 1] (or None), and an optional proof (the premise facts);
  3. answer a query "subject relation ?" with the facts it holds for it (used for retention, C1);
  4. report conflicts it flags, as facts (optional);
  5. report its cost: wall seconds and peak resident memory (MB).

It never reads rules, tiers, n/k, inference rounds or templates. An adapter maps one engine onto this contract;
`EGMAdapter` is the one for voltex2, through the SDK. Trivial baselines (baselines.py) implement the same contract.
"""
import os, sys, time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
import egm  # noqa: E402

Fact = Tuple[str, str, str]   # (relation, subject, object)


@dataclass
class Answer:
    fact: Fact
    status: str                      # "stated" | "derived"
    confidence: Optional[float]      # higher = more confident; None = the engine gives none
    proof: List[Fact] = field(default_factory=list)
    rule: str = ""                   # optional (added after the freeze): the rule that produced it, as the engine names it


@dataclass
class Run:
    answers: List[Answer]            # every derived answer, plus any stated ones the engine reports
    retained: Dict[Fact, bool]       # for each probed stated fact: did "subject relation ?" return it as stated
    flagged: Set[Fact]               # stated facts the engine flags as conflicting
    seconds: float
    peak_mb: Optional[float]
    admitted: Optional[Set[str]] = None   # optional (added after the freeze): rules the engine admitted, same naming as Answer.rule


def parse_fact(text: str, rels: Sequence[str]) -> Optional[Fact]:
    """Split fact text on the longest relation phrase it contains (relations sorted longest first by the caller)."""
    for rel in rels:
        k = f" {rel} "
        if k in text:
            a, b = text.split(k, 1)
            a, b = a.strip(), b.strip()
            if a and b and " " not in a and " " not in b:
                return (rel, a, b)
    return None


def _peak_mb(pid: int) -> Optional[float]:
    try:
        for l in open(f"/proc/{pid}/status"):
            if l.startswith("VmHWM:"):
                return int(l.split()[1]) / 1024.0
    except OSError:
        return None
    return None


# Confidence for an EGM answer, from what its ASK line reports. Law-tier derivations rank above tendency-tier ones;
# within a tier, the engine's score orders them. This uses only what the interface exposes (a label and a number per
# answer), so any engine that reports a label or a score is ranked the same way.
def egm_confidence(tier: str, score: Optional[float]) -> float:
    s = 0.0 if score is None else max(0.0, min(1.0, score))
    return (1.0 + s) / 2.0 if tier in ("law", "core") else s / 2.0


class EGMAdapter:
    """voltex2 through the SDK. settings: engine settings; strict_filter: keep only what the SDK's strict policy keeps."""

    def __init__(self, settings: Optional[dict] = None, strict_filter: bool = False, binary: Optional[str] = None,
                 policy=None):
        self.settings = dict(settings or {}); self.policy = policy
        self.strict_filter = strict_filter
        self.binary = binary or os.environ.get("VOLTEX", os.path.join(ROOT, "build", "voltex2"))

    def run(self, lines: Sequence[str], rels: Sequence[str], probes: Sequence[Fact]) -> Run:
        rels = sorted(rels, key=len, reverse=True)
        t0 = time.time()
        e = egm.Engine(binary=self.binary, settings=self.settings)
        try:
            e.ingest_many(lines)
            if self.policy is not None:
                e.apply_policy(self.policy)
            derived = e.infer_all()                       # every derived fact, with its tier
            # one ASK per (subject, relation) that has a derived answer: gives each answer's score and proof
            patterns = sorted({(d.subject, d.relation) for d in derived})
            seen = {}
            for subj, rel in patterns:
                for f in e.ask(f"{subj} {rel} ?"):
                    if f.status == "inferred":
                        seen[f.fact] = f
            answers = []
            for d in derived:
                f = seen.get(d.fact, d)
                fx = parse_fact(d.fact, rels)
                if fx is None:
                    continue
                if self.strict_filter and d.tier not in ("law", "core"):
                    continue
                proof = [p for p in (parse_fact(b, rels) for b in (f.because or [])) if p]
                # under a policy, rank by the weakest evidence on the proof (DESIGN 3.4); under legacy, by the score
                answers.append(Answer(fx, "derived", egm_confidence(d.tier, d.weakest if d.weakest is not None else f.score), proof,
                                      f.rule if f is not d else ""))
            retained = {}
            for rel, a, b in probes:                       # C1: is a stated fact returned as stated?
                got = e.ask(f"{a} {rel} ?")
                retained[(rel, a, b)] = any(parse_fact(g.fact, rels) == (rel, a, b) and g.status in ("stated", "current")
                                            for g in got)
            flagged = set()
            for c in e.conflicts():
                raw = c.raw
                if "stated: " in raw:
                    ft = raw.split("stated: ", 1)[1].split(" | ")[0]
                    fx = parse_fact(ft, rels)
                    if fx:
                        flagged.add(fx)
            ev = e.evidence()
            admitted = {v["rule"] for v in ev if (v["admit"] in ("core", "extension") if self.policy not in (None, "legacy") else v["accepted"])}
            peak = _peak_mb(e._p.pid)
        finally:
            e.close()
        return Run(answers, retained, flagged, time.time() - t0, peak, admitted)
