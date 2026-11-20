"""Parsers from engine text output to result types. Kept separate so they can be tested on fixed text."""
import re

from .model import Category, Conflict, Fact, Prediction, Relation, Rule

_STATUS = "stated|current|inferred|historical|corrected|superseded|withdrawn"
_ASK = re.compile(rf"^  (?P<fact>\S.*?)\s+(?P<status>{_STATUS})\b(?P<rest>.*)$")
_FLAGS = [("STALE", "stale"), ("SOURCES DISAGREE", "sources_disagree"), ("UNCERTAIN", "uncertain"),
          ("CONTRADICTED", "contradicted"), ("CURRENT UNKNOWN", "current_unknown")]
_TIER = re.compile(r"\[(law|tendency)\]")
_SCORE = re.compile(r"\(score ([0-9.]+)\)|score=([0-9.]+)")
_BECAUSE = re.compile(r"because (.+?)\s+\[rule: (.+?\))\](?:\s+\((.*)\))?\s*$")
_BECAUSE_PLAIN = re.compile(r"because (.+?)\s*$")
_SOURCE = re.compile(r"\(per ([^)\s]+)\)|held per (\S+)|never held per (\S+)")


def _split(fact):
    t = fact.split()
    return (t[0], " ".join(t[1:-1]), t[-1]) if len(t) >= 3 else None


def fact_line(line):
    """Parse one ASK line, or None if it is not a fact."""
    m = _ASK.match(line)
    if not m:
        return None
    fact = " ".join(m.group("fact").split())
    parts = _split(fact)
    if not parts:
        return None
    rest = m.group("rest").strip()
    f = Fact(fact=fact, subject=parts[0], relation=parts[1], object=parts[2], status=m.group("status"), raw=line.strip())
    for text, flag in _FLAGS:
        if rest.startswith(f", {text}"):
            f.flag = flag
            f.note = rest[len(text) + 2:].lstrip(":, ").strip()
            break
    else:
        f.note = rest.lstrip(":, ").strip()
    t = _TIER.search(rest); f.tier = t.group(1) if t else ""
    s = _SCORE.search(rest)
    if s:
        f.score = float(s.group(1) or s.group(2))
    if "because" in rest:
        b = _BECAUSE.search(rest)
        chain = b.group(1) if b else _BECAUSE_PLAIN.search(rest).group(1)
        if b:
            f.rule = b.group(2)
            if b.group(3):
                f.note = b.group(3)                       # e.g. "1 of 1 paths agree"
        if "; now " in chain:                             # a current value after a change: "STALE: ...; now a + b"
            f.note, chain = chain.split("; now ", 1)
        f.because = [x.strip() for x in chain.split(" + ")]
    so = _SOURCE.search(rest)
    if so:
        f.source = next(g for g in so.groups() if g)
        if f.note == f"(per {f.source})":
            f.note = ""
    return f


def ask(lines):
    return [f for f in (fact_line(l) for l in lines) if f]


def infer_all(lines):
    out = []
    for l in lines:
        if not l.startswith("FACT\t"):
            continue
        p = l.split("\t")
        parts = _split(p[1])
        if parts:
            out.append(Fact(fact=p[1], subject=parts[0], relation=parts[1], object=parts[2], status="inferred",
                            tier=p[2] if len(p) > 2 else "", raw=l))
    return out


_REL = re.compile(r"^\s+#(\d+)\s+(.+?)\s{2,}(\d+) facts\s*$")
_RULE = re.compile(r"^\s+(ACCEPT|reject) (.+?)\s+n=(\d+) k=(\d+) rate=([0-9.]+) lift=([0-9.]+)"
                   r"(?: \| where answer known: (\d+), agree=([0-9.]+))?(.*)$")


_PREMISE = re.compile(r"\[\? .+? \?\]\(")


def rule_shape(text):
    """(shape, premise count, condition) of a rule's text, e.g. 'TREE [? a ?](a,g) & ... => ...'."""
    body, _, head = text.partition(" => ")
    condition = head.split(" if ", 1)[1].strip() if " if " in head else ""
    premises = len(_PREMISE.findall(body))
    if body.startswith("TREE "):
        shape = "tree"
    elif premises <= 1:
        shape = "inverse"
    elif premises == 2:
        shape = "chain"
    else:
        shape = "path"
    return shape, premises, condition


def relations(lines):
    out = []
    for l in lines:
        m = _REL.match(l)
        if m:
            tmpl = m.group(2).strip()
            w = tmpl.split()
            out.append(Relation(index=int(m.group(1)), template=tmpl, relation=" ".join(w[1:-1]), facts=int(m.group(3))))
    return out


def rules(lines):
    out = []
    for l in lines:
        m = _RULE.match(l)
        if m:
            tier = re.search(r"tier=(\w+)", m.group(9) or "")
            text = m.group(2).strip()
            shape, premises, condition = rule_shape(text)
            out.append(Rule(accepted=m.group(1) == "ACCEPT", text=text, n=int(m.group(3)), k=int(m.group(4)),
                            rate=float(m.group(5)), lift=float(m.group(6)),
                            known=int(m.group(7)) if m.group(7) else None, agree=float(m.group(8)) if m.group(8) else None,
                            tier=tier.group(1) if tier else "", raw=l.strip(), shape=shape, premises=premises, condition=condition))
    return out


_PRED = re.compile(r"^\s+(\S+)\s+p=([0-9.]+)\s+(observed|inferred via categories)\s*$")


def predictions(lines):
    out = []
    for l in lines:
        m = _PRED.match(l)
        if m:
            out.append(Prediction(token=m.group(1), p=float(m.group(2)), observed=m.group(3) == "observed"))
    return out


_CAT = re.compile(r"^\s+(C\d+) \((\d+)\): (.*)$")


def categories(lines):
    out = []
    for l in lines:
        m = _CAT.match(l)
        if m:
            out.append(Category(id=m.group(1), size=int(m.group(2)), members=m.group(3).split()))
    return out


def conflicts(lines):
    out = []
    for l in lines:
        if l.startswith("CONFLICT\t"):
            p = l.split("\t", 3)
            out.append(Conflict(subject=p[1], stated=p[2], detail=p[3] if len(p) > 3 else "", raw=l))
    return out


def metrics(lines):
    out = {}
    for l in lines:
        if ":" in l and not l.startswith("---"):
            k, v = l.split(":", 1)
            out[k.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")] = v.strip()
    return out


_CFG = re.compile(r"^\[CONFIG\] (\S+)\s+(\S+)\s+\(default (\S+)\)\s+(\S+)\s+(EXPERIMENTAL )?(.*)$")


def config(lines):
    out = {}
    for l in lines:
        m = _CFG.match(l)
        if m:
            out[m.group(1)] = {"value": float(m.group(2)), "default": float(m.group(3)), "layer": m.group(4),
                               "experimental": bool(m.group(5)), "help": m.group(6).strip()}
    return out
