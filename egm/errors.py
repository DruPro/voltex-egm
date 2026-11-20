"""Exceptions. Everything the SDK raises derives from EgmError."""


class EgmError(Exception):
    """Base class for SDK errors."""


class EngineNotFound(EgmError, FileNotFoundError):
    """The voltex2 binary could not be located."""


class EngineError(EgmError, RuntimeError):
    """The engine rejected a command, failed to load or save, or exited."""


class RelationNotLearned(EgmError, LookupError):
    """ASK named a relation the engine has not learned (too few facts: it needs 3+ with 2+ names per slot)."""

    def __init__(self, relation, learned):
        self.relation, self.learned = relation, list(learned)
        super().__init__(f"'{relation}' is not a learned relation. A relation needs at least 3 facts of the form "
                         f"'A {relation} B', with at least 2 different words in each slot. "
                         f"Learned relations: {', '.join(self.learned) if self.learned else 'none yet'}")
