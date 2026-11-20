"""The Engine: a persistent voltex2 process with typed methods.

    import egm
    with egm.open("kb.vtx") as kb:                    # or a facts .txt file, or egm.Engine()
        for f in kb.ask("? calls requests__select_proxy"):
            print(f.subject, f.status, f.tier)

The knowledge base is loaded once; every call after that is a pipe round trip.
An Engine is not thread-safe: use one per thread, or guard it with a lock.
"""
import os
import secrets
import shutil
import subprocess
import tempfile
from typing import Iterable, List, Optional, Sequence

from . import parse
from .errors import EngineError, EngineNotFound, RelationNotLearned
from .model import Category, Conflict, Fact, Prediction, Relation, Rule

_HERE = os.path.dirname(os.path.abspath(__file__))


def find_binary(explicit: Optional[str] = None) -> str:
    """Locate voltex2: explicit path > $VOLTEX > bundled (pip install) > source checkout build/ > PATH."""
    if explicit:
        if os.path.isfile(explicit) and os.access(explicit, os.X_OK):
            return os.path.abspath(explicit)
        raise EngineNotFound(f"voltex2 not found at {explicit}")
    cands = [os.environ.get("VOLTEX"),
             os.path.join(_HERE, "_bin", "voltex2"),
             os.path.join(_HERE, "_bin", "voltex2.exe"),
             os.path.join(_HERE, "..", "build", "voltex2"),
             shutil.which("voltex2")]
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return os.path.abspath(c)
    raise EngineNotFound("voltex2 binary not found. pip install the kit (it compiles the engine), run `make`, "
                         "set VOLTEX=/path/to/voltex2, or put voltex2 on PATH.")


def _relation_of(pattern: str) -> str:
    w = pattern.split()
    return " ".join(w[1:-1]) if len(w) >= 3 else ""


class Engine:
    """A running engine.

    Args:
        kb: a saved knowledge base (.vtx) to load.
        facts: facts files to ingest (one ``A relation B`` per line).
        binary: path to voltex2 (otherwise found automatically).
        settings: engine settings, applied after ``kb`` is loaded so they override the profile saved with it,
            e.g. ``{"RATE": 0.4, "DEPTH": 0}``. ``config()`` lists every setting.
    """

    def __init__(self, kb: Optional[str] = None, facts: Iterable[str] = (), binary: Optional[str] = None,
                 settings: Optional[dict] = None):
        self.binary = find_binary(binary)
        v = subprocess.run([self.binary, "--version"], capture_output=True, text=True).stdout.split()
        if len(v) < 2 or tuple(int(x) for x in v[1].split(".")[:3]) < (2, 2, 1):
            raise EngineError(f"{self.binary} is too old for the SDK (needs voltex2 2.2.1+, which adds ECHO and --version)")
        self._marker = f"__egm_end_{secrets.token_hex(8)}__"     # ends every reply; random so no output can imitate it
        self._p = subprocess.Popen([self.binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        try:
            if kb:
                self.load(kb)            # restores the profile saved with the knowledge base (kb.vtx.cfg), if any
            for k, v in (settings or {}).items():
                self.set(k, v)           # explicit settings override the saved profile
            for f in facts:
                self.ingest_file(f)
        except Exception:
            self.close()
            raise

    @classmethod
    def open(cls, path: str, **kw) -> "Engine":
        """Open a saved knowledge base, or ingest a facts file if ``path`` ends in .txt."""
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        return cls(facts=[path], **kw) if path.endswith(".txt") else cls(kb=path, **kw)

    # --- protocol -----------------------------------------------------------------------
    def cmd(self, line: str) -> List[str]:
        """Send one raw engine command (any of HELP's commands); return its output lines."""
        if "\n" in line or "\r" in line:
            raise ValueError("one command per call (no newlines)")
        if self._p.poll() is not None:
            raise EngineError("engine is closed")
        try:
            self._p.stdin.write(line + "\n" + "ECHO " + self._marker + "\n")
            self._p.stdin.flush()
        except BrokenPipeError:
            raise EngineError(f"engine exited before: {line}") from None
        out = []
        while True:
            l = self._p.stdout.readline()
            if l == "":
                raise EngineError(f"engine exited while running: {line}\n" + "\n".join(out[-20:]))
            l = l.rstrip("\n")
            if l == self._marker:
                return out
            out.append(l)

    def _checked(self, line: str) -> List[str]:
        out = self.cmd(line)
        for l in out:
            if l.startswith("[ERROR]"):
                raise EngineError(f"{line}: {l[8:]}")
        return out

    # --- adding evidence ----------------------------------------------------------------
    def ingest(self, fact: str) -> int:
        """Store one record; returns its id (the same text always gets the same id)."""
        for l in self._checked(f"INGEST {fact}"):
            if l.startswith("[INGEST] id "):
                return int(l.split()[-1])
        raise EngineError(f"unexpected reply to INGEST {fact}")

    def ingest_many(self, facts: Iterable[str]) -> int:
        """Store many records in one call (through a temporary file). Returns the number of lines sent."""
        facts = [f.strip() for f in facts if f.strip()]
        if any("\n" in f for f in facts):
            raise ValueError("a fact cannot contain a newline")
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="egm_")
        try:
            with os.fdopen(fd, "w") as fh:
                fh.write("\n".join(facts) + "\n")
            self.ingest_file(path)
        finally:
            os.unlink(path)
        return len(facts)

    def ingest_file(self, path: str) -> List[str]:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        return self._checked(f"INGESTFILE {os.path.abspath(path)}")

    def observe(self, source: str, record: str, time: int, revision: int = 1, scope: str = "snapshot",
                facts: Sequence[str] = ()) -> None:
        """Add source-aware evidence.

        scope="snapshot": ``facts`` is everything ``record`` states now; facts it no longer states become history.
        scope="partial": ``facts`` are added; nothing is withdrawn.
        """
        if scope not in ("snapshot", "partial"):
            raise ValueError("scope must be 'snapshot' or 'partial'")
        for x in (source, record):
            if not x or any(c.isspace() for c in x) or "|" in x:
                raise ValueError(f"source and record must be non-empty, without spaces or '|': {x!r}")
        if any(";" in f or "|" in f for f in facts):
            raise ValueError("a fact cannot contain ';' or '|'")
        self._checked(f"OBSERVE {source} {record} {int(time)} {int(revision)} {scope} | " + " ; ".join(facts))

    def retract(self, fact: str) -> bool:
        """Remove a stored record. Returns False if it was not stored."""
        return any("removed" in l for l in self._checked(f"RETRACT {fact}"))

    def update(self, fact: str) -> List[str]:
        """Replace the subject's previous value in a one-value relation, then store ``fact``."""
        return self._checked(f"UPDATE {fact}")

    # --- asking -------------------------------------------------------------------------
    def ask(self, pattern: str, strict: bool = False, require: bool = False) -> List[Fact]:
        """Answer a pattern; ``?`` marks the slot(s) to fill, e.g. ``"? calls mypkg__connect"``.

        Returns current facts, inferences with proofs and history lines (see ``Fact.status``).
        strict: keep only stated/current facts and law-tier inferences.
        require: raise RelationNotLearned instead of returning [] when the relation is unknown.
        """
        facts = parse.ask(self._checked(f"ASK {pattern}"))
        if not facts and require:
            rel = _relation_of(pattern)
            learned = [r.relation for r in self.relations()]
            if rel and rel not in learned:
                raise RelationNotLearned(rel, learned)
        return [f for f in facts if f.is_strict] if strict else facts

    def current(self, pattern: str, strict: bool = False) -> List[Fact]:
        """Only what holds now."""
        return [f for f in self.ask(pattern, strict=strict) if f.is_current]

    def history(self, pattern: str) -> List[Fact]:
        """Only past values: historical, corrected, superseded and withdrawn facts."""
        return [f for f in self.ask(pattern) if f.is_history]

    def values(self, pattern: str, strict: bool = False) -> List[str]:
        """The filled slot of each current answer, sorted: ``values("x calls ?")`` -> callee names."""
        w = pattern.split()
        take = (lambda f: f.object) if w and w[-1] == "?" else (lambda f: f.subject)
        return sorted({take(f) for f in self.current(pattern, strict=strict)})

    def explain(self, pattern: str) -> Optional[str]:
        """Why a pattern has no answer, or None if it has one."""
        if self.ask(pattern):
            return None
        rel = _relation_of(pattern)
        learned = [r.relation for r in self.relations()]
        if rel and rel not in learned:
            return str(RelationNotLearned(rel, learned))
        return "no stated or inferred answer"

    def infer_all(self) -> List[Fact]:
        """Every fact derived by accepted rules."""
        return parse.infer_all(self._checked("INFER ALL"))

    def conflicts(self) -> List[Conflict]:
        return parse.conflicts(self._checked("CONFLICTS"))

    # --- what was learned ---------------------------------------------------------------
    def relations(self) -> List[Relation]:
        return parse.relations(self._checked("RELATIONS"))

    def rules(self, include_rejected: bool = False) -> List[Rule]:
        r = parse.rules(self._checked("RELATIONS"))
        return r if include_rejected else [x for x in r if x.accepted]

    def categories(self, threshold: Optional[float] = None) -> List[Category]:
        """Word categories induced from shared contexts (``threshold`` changes the merge level)."""
        return parse.categories(self._checked("CLASSES" + (f" {threshold}" if threshold is not None else "")))

    def metrics(self) -> dict:
        return parse.metrics(self._checked("METRICS"))

    # --- the language-model face --------------------------------------------------------
    def predict(self, prefix: str) -> List[Prediction]:
        """Most likely next words after ``prefix`` (top 10)."""
        return parse.predictions(self._checked(f"PREDICT {prefix}"))

    def query(self, pattern: str) -> List[Prediction]:
        """Most likely fillers for one ``?`` slot by sequence statistics (not rules), e.g. ``"the blue ?"``."""
        return parse.predictions(self._checked(f"QUERY {pattern}"))

    def generate(self, prefix: str = "") -> str:
        """Continue ``prefix`` by sampling the grammar (deterministic for a given state)."""
        for l in self._checked(f"GENERATE {prefix}".rstrip()):
            if l.startswith("[GENERATE] "):
                return l[11:]
        return ""

    def sample(self, n: int = 5) -> List[str]:
        """``n`` sentences sampled from the grammar."""
        return [l.split("\t", 1)[1] for l in self._checked(f"SAMPLE {int(n)}") if l.startswith("GEN\t")]

    # --- records ------------------------------------------------------------------------
    def find(self, text: str) -> Optional[int]:
        for l in self._checked(f"FIND {text}"):
            if l.startswith("[FIND] id "):
                return int(l.split()[-1])
        return None

    def unroll(self, record_id: int) -> str:
        out = self._checked(f"UNROLL {int(record_id)}")
        return out[0] if out else ""

    def __contains__(self, text: str) -> bool:
        return self.find(text) is not None

    # --- settings and persistence -------------------------------------------------------
    def config(self) -> dict:
        """Every engine setting: {name: {"value", "default", "layer", "experimental", "help"}}."""
        return parse.config(self._checked("CONFIG"))

    def set(self, key: str, value) -> None:
        """Engine setting, e.g. ``set("RATE", 0.4)``. See ``SET`` in the engine's HELP for the list."""
        out = self._checked(f"SET {key} {value}")
        if not any(l.startswith("[SET]") and "=" in l for l in out):
            raise ValueError(f"unknown setting {key}: " + " ".join(out))

    def save(self, path: str) -> None:
        out = self._checked(f"SAVE {os.path.abspath(path)}")
        if "[SAVE] ok" not in out:
            raise EngineError(f"save failed: {path}")

    def load(self, path: str) -> None:
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        out = self.cmd(f"LOAD {os.path.abspath(path)}")
        if "[LOAD] ok" not in out:
            raise EngineError(f"could not load {path}: " + " ".join(out))

    def version(self) -> str:
        return subprocess.run([self.binary, "--version"], capture_output=True, text=True).stdout.strip()

    def close(self) -> None:
        p = getattr(self, "_p", None)
        if p and p.poll() is None:
            try:
                p.stdin.write("EXIT\n"); p.stdin.flush(); p.wait(timeout=5)
            except Exception:
                p.kill(); p.wait()
        for s in (getattr(p, "stdin", None), getattr(p, "stdout", None)):
            try:
                s and s.close()
            except Exception:
                pass

    @property
    def closed(self) -> bool:
        return self._p.poll() is not None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
