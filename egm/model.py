"""Result types returned by the SDK. All are plain dataclasses: compare, print, or `.to_dict()` them."""
from dataclasses import asdict, dataclass, field
from typing import List, Optional

#: ASK statuses. ``stated``/``current``/``inferred`` describe what holds now; the rest are history.
CURRENT_STATUSES = ("stated", "current", "inferred")
HISTORY_STATUSES = ("historical", "corrected", "superseded", "withdrawn")


class _Dict:
    def to_dict(self):
        return asdict(self)


@dataclass
class Fact(_Dict):
    """One line of an ASK answer (or of INFER ALL).

    status  stated | current | inferred | historical | corrected | superseded | withdrawn
    flag    "" or stale | sources_disagree | uncertain | contradicted | current_unknown | outvoted | quarantined
    tier    law | tendency (inferred facts only)
    """
    fact: str
    subject: str
    relation: str
    object: str
    status: str
    flag: str = ""
    tier: str = ""
    score: Optional[float] = None
    because: List[str] = field(default_factory=list)
    rule: str = ""
    source: str = ""
    note: str = ""
    raw: str = ""

    @property
    def is_current(self) -> bool:
        """Holds now: stated (and not stale), the current value after a change, or inferred."""
        return self.status in CURRENT_STATUSES and self.flag != "stale"

    @property
    def is_history(self) -> bool:
        return self.status in HISTORY_STATUSES

    @property
    def is_strict(self) -> bool:
        """The strict policy: stated or current facts, plus law-tier inferences."""
        return (self.status in ("stated", "current") and self.flag != "stale") or (self.status == "inferred" and self.tier == "law")


@dataclass
class Relation(_Dict):
    """A learned two-slot template such as ``? calls ?``."""
    index: int
    template: str
    relation: str
    facts: int


@dataclass
class Rule(_Dict):
    """A candidate rule between relations, with the evidence it was scored on."""
    accepted: bool
    text: str
    n: int                      # chains seen
    k: int                      # chains whose conclusion is also stated
    rate: float
    lift: float
    known: Optional[int] = None  # chains where the answer is known
    agree: Optional[float] = None
    tier: str = ""
    raw: str = ""
    shape: str = ""             # inverse | chain (two premises) | path (3+ premises, CHAIN) | tree (TREES)
    premises: int = 0           # number of premise facts in the rule's body
    condition: str = ""         # CONDITIONS: the group the rule is restricted to, e.g. "[? works as ?](a,farmer|miner)"
    replication: str = ""       # REPLICATE: why the rule was rejected, e.g. "did not replicate (half A: ...; half B: ...)"


@dataclass
class Prediction(_Dict):
    """A candidate next word (PREDICT) or slot filler (QUERY)."""
    token: str
    p: float
    observed: bool              # False: inferred via word categories


@dataclass
class Category(_Dict):
    id: str
    size: int
    members: List[str]


@dataclass
class Conflict(_Dict):
    """A stated fact that the rules contradict, or a source disagreement / uncertainty."""
    subject: str
    stated: str                 # "-" when there is no single stated value
    detail: str
    raw: str = ""
    kind: str = ""              # value (rules infer another value) | quarantined (QUARANTINE) | outvoted (VOTE) | other
