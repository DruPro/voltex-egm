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

import contextlib

from . import parse
from . import policy as _policy
from .errors import EngineError, EngineNotFound, RelationNotLearned
from .model import Category, Conflict, Fact, PolicyComparison, Prediction, Relation, Rule

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
        self.policy = _policy.BUILTINS["legacy"]       # the policy inference runs under (POLICY APPLY); legacy = none
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
    def ask(self, pattern: str, strict: bool = False, require: bool = False, policy=None,
            legacy_strict: bool = False) -> List[Fact]:
        """Answer a pattern; ``?`` marks the slot(s) to fill, e.g. ``"? calls mypkg__connect"``.

        Returns current facts, inferences with proofs and history lines (see ``Fact.status``).
        strict: stated/current facts and strict inferences only. Under legacy this runs the query under the engine's
            built-in ``strict`` policy (voltex3): its answers are closed, every premise of a proof is itself an answer.
            (Before voltex3 it filtered legacy answers to law-tier ones, which could keep a fact whose premise it
            dropped; docs/POLICIES.md, "SDK correction".) Under another policy it keeps that policy's core stratum,
            which is closed by construction.
        require: raise RelationNotLearned instead of returning [] when the relation is unknown.
        policy: run this query under a policy (name, "name@version" or Policy); the engine's policy is restored after.
        legacy_strict: the pre-voltex3 strict filter (stated/current facts and law-tier legacy inferences), kept as a
            compatibility alias until a major version (Mimic relies on it). Not closed: it can keep a fact whose premise
            it drops. Not used by any evaluation.
        """
        if legacy_strict:
            if strict or policy is not None:
                raise ValueError("legacy_strict can't be combined with strict or policy")
            facts = self.ask(pattern, require=require)
            return [f for f in facts if (f.status in ("stated", "current") and f.flag != "stale") or
                    (f.status == "inferred" and f.tier == "law")]
        if strict and policy is None and self.policy.is_legacy:
            policy = _policy.BUILTINS["strict"]
        with self._policy_scope(policy):
            facts = parse.ask(self._checked(f"ASK {pattern}"))
            for f in facts:
                f.policy = self.policy.id
        if not facts and require:
            rel = _relation_of(pattern)
            learned = [r.relation for r in self.relations()]
            if rel and rel not in learned:
                raise RelationNotLearned(rel, learned)
        return [f for f in facts if f.is_strict] if strict else facts

    def current(self, pattern: str, strict: bool = False, legacy_strict: bool = False) -> List[Fact]:
        """Only what holds now."""
        return [f for f in self.ask(pattern, strict=strict, legacy_strict=legacy_strict) if f.is_current]

    def history(self, pattern: str) -> List[Fact]:
        """Only past values: historical, corrected, superseded and withdrawn facts."""
        return [f for f in self.ask(pattern) if f.is_history]

    def values(self, pattern: str, strict: bool = False, legacy_strict: bool = False) -> List[str]:
        """The filled slot of each current answer, sorted: ``values("x calls ?")`` -> callee names."""
        w = pattern.split()
        take = (lambda f: f.object) if w and w[-1] == "?" else (lambda f: f.subject)
        return sorted({take(f) for f in self.current(pattern, strict=strict, legacy_strict=legacy_strict)})

    def explain(self, pattern: str) -> Optional[str]:
        """Why a pattern has no answer, or None if it has one."""
        if self.ask(pattern):
            return None
        rel = _relation_of(pattern)
        learned = [r.relation for r in self.relations()]
        if rel and rel not in learned:
            return str(RelationNotLearned(rel, learned))
        return self.unknown_note()

    def unknown_note(self) -> str:
        """What an empty answer means: unknown, not false. Under a cap ([LIMIT] lines, e.g. MAXWORDS) the answer may
        exist beyond it, and the note says so instead of letting silence read as "no"."""
        lim = self.limits()
        note = "no stated or inferred answer: unknown, not false"
        if lim:
            note += "; this knowledge base is capped (" + "; ".join(lim) + "), so the name may lie beyond the cap"
        return note

    def infer_all(self, policy=None) -> List[Fact]:
        """Every fact derived by accepted rules (under ``policy`` if given; each Fact names the policy it ran under)."""
        with self._policy_scope(policy):
            facts = parse.infer_all(self._checked("INFER ALL"))
            for f in facts:
                f.policy = self.policy.id
        return facts

    # --- policies -----------------------------------------------------------------------
    def apply_policy(self, policy, registry: Optional["_policy.PolicyRegistry"] = None) -> "_policy.Policy":
        """Run inference under ``policy`` from now on: a name, "name@version" or a Policy (``legacy`` = no policy).
        Validated before it reaches the engine; the evidence is not changed."""
        p = (registry or _policy.policies).get(policy) if not isinstance(policy, _policy.Policy) else policy
        self._checked(p.engine_command())
        self.policy = p
        return p

    @contextlib.contextmanager
    def _policy_scope(self, policy):
        if policy is None:
            yield; return
        prev = self.policy
        self.apply_policy(policy)
        try:
            yield
        finally:
            self.apply_policy(prev)

    def snapshot(self) -> str:
        """An identifier of the exact evidence state (records, counts, observation log). Policies never change it."""
        for l in self._checked("SNAPSHOT"):
            if l.startswith("[SNAPSHOT] "):
                return l.split()[1]
        raise EngineError("no SNAPSHOT reply")

    def compare_policies(self, policies, registry: Optional["_policy.PolicyRegistry"] = None) -> PolicyComparison:
        """Run several policies on the same evidence snapshot and compare what each derives."""
        reg = registry or _policy.policies
        ps = [reg.get(p) if not isinstance(p, _policy.Policy) else p for p in policies]
        snap = self.snapshot(); facts, summary = {}, []
        for p in ps:
            fs = self.infer_all(policy=p)
            with self._policy_scope(p):
                ev = self.evidence()
            facts[p.id] = sorted(f.fact for f in fs)
            summary.append({"policy": p.id, "derived": len(fs),
                            "core": sum(1 for f in fs if f.tier == "core"),
                            "extension": sum(1 for f in fs if f.tier == "extension"),
                            "rules_core": sum(1 for v in ev if v["admit"] == "core"),
                            "rules_extension": sum(1 for v in ev if v["admit"] == "extension"),
                            "rules_accepted": sum(1 for v in ev if v["accepted"])})
        if self.snapshot() != snap:
            raise EngineError("the evidence changed during the comparison")
        contained = {f"{a} in {b}": set(facts[a]) <= set(facts[b]) for a in facts for b in facts if a != b}
        return PolicyComparison(snap, [p.id for p in ps], summary, facts, contained)

    def conflicts(self) -> List[Conflict]:
        return parse.conflicts(self._checked("CONFLICTS"))

    # --- what was learned ---------------------------------------------------------------
    def relations(self) -> List[Relation]:
        return parse.relations(self._checked("RELATIONS"))

    def rules(self, include_rejected: bool = False, shape: Optional[str] = None) -> List[Rule]:
        """Learned rules. ``shape`` filters: "inverse", "chain", "path" (SET CHAIN >= 3) or "tree" (SET TREES 1);
        a rule restricted to a group (SET CONDITIONS 1) has ``condition`` set."""
        r = parse.rules(self._checked("RELATIONS"))
        if not include_rejected:
            r = [x for x in r if x.accepted]
        return [x for x in r if x.shape == shape] if shape else r

    def evidence(self, include_rejected: bool = False) -> List[dict]:
        """voltex3: each rule's evidence vector (RULES EVIDENCE): {"accepted", "rule", "n", "e_plus", "e_minus",
        "e_unknown", "agree", "lift", "z", "base", "cov", "rel", "tier", "one_value", "validation", "admit"}: validation is
        "<method>:pass|fail|not_run" (an evaluation, not a property of the rule); admit is the stratum of the active
        policy that admits the rule (core, extension, none; "-" under legacy). E- is defined only for one-value
        conclusion relations (else 0: a missing conclusion there is unknown, not opposing); agree is None when no answer
        is known."""
        out = []
        for l in self._checked("RULES EVIDENCE" + (" ALL" if include_rejected else "")):
            if not l.startswith("EVIDENCE\t"):
                continue
            p = l.split("\t"); kv = dict(x.split("=", 1) for x in p[3:])
            out.append({"accepted": p[1] == "ACCEPT", "rule": p[2], "n": int(kv["n"]), "e_plus": int(kv["e+"]),
                        "e_minus": int(kv["e-"]), "e_unknown": int(kv["e?"]),
                        "agree": None if kv["agree"] == "undef" else float(kv["agree"]), "lift": float(kv["lift"]),
                        "z": float(kv["z"]), "base": float(kv["base"]), "cov": float(kv["cov"]), "rel": float(kv["rel"]),
                        "tier": kv["tier"], "one_value": kv["one_value"] == "1",
                        "validation": kv.get("validation", ""), "admit": kv.get("admit", "-"),
                        "cov_source": kv.get("cov_source"),
                        "cov_source_agree": None if kv.get("cov_source_agree", "undef") == "undef" else float(kv["cov_source_agree"]),
                        "stability": None if kv.get("stability", "undef") == "undef" else float(kv["stability"])})
        return out

    def chains(self) -> List[dict]:
        """How each derived fact was reached: {"fact", "round", "tendency_steps"} (rounds count from 1; tendency steps
        are tendency-tier rule steps anywhere in its proof). See SET TENDENCYSTEPS."""
        return parse.chains(self._checked("CHAINS ALL"))

    def limits(self) -> List[str]:
        """Capacity limits the last build hit (e.g. more words than MAXWORDS), as the engine reports them."""
        return [l[len("[LIMIT] "):] for l in self._checked("RELATIONS") if l.startswith("[LIMIT] ")]

    def experimental(self) -> dict:
        """Experimental settings that are currently not at their default: {name: value}."""
        return {k: v["value"] for k, v in self.config().items() if v["experimental"] and v["value"] != v["default"]}

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
