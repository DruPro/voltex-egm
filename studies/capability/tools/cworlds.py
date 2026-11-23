"""Worlds for the capability suite, each with its complete truth.

Nothing here is new world logic: worlds come from the existing generators (studies/noise/hidden/gen.py through
studies/noise/tools/lib.py, and tests/worlds.py through studies/eval/tools/scorecard.py). Added on top:

  - the key is the world's full truth, not what designed rules produce;
  - `undeterminable`: (relation, subject) queries whose true answer does not follow from the observations, where the
    generator lets us compute it (None = not labelled for this world; reported as such, never guessed);
  - `matched`: the setting that switches on the engine's shape for this structure (used only in the 'matched' profile,
    which is labelled as tuned per structure).
"""
import os, sys
from dataclasses import dataclass, field
from typing import Optional, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "tools"))
sys.path.insert(0, os.path.join(ROOT, "studies", "eval", "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import lib        # noqa: E402
import scorecard  # noqa: E402

from interface import parse_fact  # noqa: E402


@dataclass
class World:
    name: str
    structure: str
    seed: int
    lines: list
    rels: list
    truth: Set[Tuple[str, str, str]]
    unseen: Set[str] = field(default_factory=set)
    corrupted: Set[Tuple[str, str, str]] = field(default_factory=set)
    undeterminable: Optional[Set[Tuple[str, str]]] = None
    matched: dict = field(default_factory=dict)


# name, structure, source, generator name, generator args, matched setting
CATALOGUE = [
    ("company", "composition and inverse", "noise", "company", {"scale": 1}, {}),
    ("company-noise15", "noisy evidence", "noise", "company", {"scale": 1, "noise": 0.15}, {}),
    ("hidden-cov30", "incomplete evidence (30%)", "noise", "hidden", {"scale": 1, "coverage": 0.3}, {}),
    ("hidden-cov50", "incomplete evidence (50%)", "noise", "hidden", {"scale": 1, "coverage": 0.5}, {}),
    ("hidden-cov70", "incomplete evidence (70%)", "noise", "hidden", {"scale": 1, "coverage": 0.7}, {}),
    ("gates", "branching (trees)", "noise", "gates", {"per_kind": 200}, {"TREES": 1}),
    ("lineage", "multi-premise path", "noise", "lineage", {}, {"CHAIN": 3}),
    ("harvest", "conditional", "tests", "harvest", {}, {"CONDITIONS": 1}),
    ("remainders", "long chains (depth)", "tests", "remainders", {}, {"DEPTH": 0}),
    ("random_links", "control: no structure", "tests", "random_links", {}, {}),
]


def _remainder_undeterminable(lines):
    """A number's remainder follows from the observations only through a taught number below it in steps of 3."""
    taught = {}
    for l in lines:
        p = l.split()
        if len(p) == 4 and p[1:3] == ["has", "remainder"]:
            taught[int(p[0][1:])] = p[3]
    nums = set()
    for l in lines:
        for tok in l.split():
            if tok.startswith("n") and tok[1:].isdigit():
                nums.add(int(tok[1:]))
    out = set()
    for n in nums:
        if n in taught:
            continue
        if not any((n - m) > 0 and (n - m) % 3 == 0 for m in taught):
            out.add(("has remainder", f"n{n}"))
    return out


def load(name, seed):
    for nm, structure, src, gname, kw, matched in CATALOGUE:
        if nm != name:
            continue
        if src == "noise":
            path, h = lib.world(gname, seed=seed, **kw)
            lines = [l for l in open(path).read().splitlines() if l.strip()]
        else:
            lines, h = scorecard.tests_world(gname, seed)
        rels = sorted(h["relations"], key=len, reverse=True)
        truth = {tuple(x) for x in h["truth"]}
        corrupted = {(c[0], c[1], c[2]) for c in h.get("corrupted", [])}
        und = None
        if gname == "remainders":
            und = _remainder_undeterminable(lines)
        elif gname in ("lineage", "gates", "harvest", "random_links"):
            und = set()    # every hidden fact follows from the observations (complete premises); nothing is hidden in random_links
        return World(nm, structure, seed, lines, rels, truth, set(h.get("unseen", [])), corrupted, und, matched)
    raise KeyError(name)


def stated(world):
    return {f for f in (parse_fact(l, world.rels) for l in world.lines) if f}
