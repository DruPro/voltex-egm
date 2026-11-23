"""EGM: Evidential Grammar Memory on the Voltex engine.

    import egm
    with egm.open("kb.vtx") as kb:
        kb.ask("? calls mypkg__connect")        # -> [Fact(...)]
        kb.values("mypkg__Client raises ?", strict=True)
        kb.rules(), kb.relations(), kb.infer_all(), kb.conflicts()
        kb.predict("mypkg__Client"), kb.generate(), kb.sample(3)

Building blocks: egm.Engine, egm.extract_python, egm.bench (questions, solver, scoring),
egm.policies (custom, versioned inference policies: egm/policy.py, docs/POLICIES.md),
egm.tune (settings for one dataset, chosen from the dataset itself), egm.shard (one engine per independent
source, one answer set tagged by source; experimental).
"""
__version__ = "2.2.1"

from .engine import Engine, find_binary
from .errors import EgmError, EngineError, EngineNotFound, RelationNotLearned
from .model import Category, Conflict, Fact, PolicyComparison, Prediction, Relation, Rule
from .policy import BUILTINS as BUILTIN_POLICIES, Policy, PolicyError, PolicyRegistry, policies
from .shard import ShardResult, shard
from .tune import DEFAULT_SPACE, TuneResult, tune


def open(path, **kw):  # noqa: A001  (mirrors builtins.open on purpose: egm.open)
    """Open a saved knowledge base (.vtx) or ingest a facts file (.txt). Use as a context manager."""
    return Engine.open(path, **kw)


__all__ = ["Policy", "PolicyRegistry", "PolicyError", "PolicyComparison", "policies", "BUILTIN_POLICIES", "Engine", "open", "find_binary", "Fact", "Relation", "Rule", "Prediction", "Category", "Conflict",
           "EgmError", "EngineError", "EngineNotFound", "RelationNotLearned", "tune", "TuneResult", "DEFAULT_SPACE", "shard", "ShardResult", "__version__"]
