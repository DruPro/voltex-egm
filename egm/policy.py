"""Inference policies: named, versioned, validated configurations of how the engine admits rules and derives facts.

A policy is an inference contract, not a mode. The engine executes any valid policy through one implementation
(``POLICY APPLY``); this module defines the configuration contract, validates it, and keeps a versioned registry. The
CLI (``egm policy ...``) uses this same module, so SDK and CLI share one implementation.

    import egm
    p = egm.policies.create("conservative", thresholds={"minAgreement": 0.9, "minSupport": 100},
                            validation={"method": "internal_replication", "required": True})
    p = egm.policies.update("conservative", thresholds={"minAgreement": 0.95})     # -> version 2; version 1 is kept
    with egm.open("facts.txt") as kb:
        facts = kb.infer_all(policy=p)                    # each Fact carries fact.policy == "conservative@2"
        cmp = kb.compare_policies(["tendency", "strict", p])

Built-in policies: ``legacy`` (the engine's behaviour before policies, byte for byte; it has no configuration),
``strict`` and ``tendency``. Built-ins can't be changed; clone one to start a custom policy.

The contract (every field is enforced by the engine; nothing here is advisory):

  thresholds   minSampleSize    cases where the rule's answer is known (pn); whole number >= 0
               minSupport       confirming cases: the conclusion is stated (E+ = k); whole number >= 0
               minAgreement     E+ / known cases; 0-1. Opposing evidence exists only in one-value relations, where a
                                known different answer contradicts the rule; elsewhere a missing conclusion is unknown
               minReliability   one-value conclusions: the agreement; several values per subject: the
                                coverage-corrected rate; 0-1
               minCoverage      estimated completeness of the conclusion relation (0 when it can't be estimated); 0-1
               minZ             agreement above chance, in standard deviations (statistical significance); any number
               minLift          rate over the conclusion's base rate; >= 0
               maxUnknownShare  E? / chains: share of chains whose answer is unknown; 0-1
               minAgreementToCoverage  several values per subject only, where a coverage estimate exists: agreement /
                                estimated completeness of the conclusion relation (a true rule is near 1); >= 0
  validation   required         true: the rule must pass validation
               method           "internal_replication" (split-half on this knowledge base; "split_half" is accepted
                                as the same method). Independent-source confirmation is not available yet.
               split            "hash" (subject names) or "blocked" (first appearance in ingestion order: use for
                                time-ordered or correlated data, e.g. markets)
               minPerHalf       fewest known answers in each half for the test to be meaningful; whole number >= 0
               onInsufficient   "reject" or "admit": a rule with too few known answers to test is insufficient, not
                                failed; this says what the policy does with it
  inference    maxDepth         inference rounds for this stratum; whole number >= 0, 0 = until nothing new
               shapes           derivation classes allowed: inverse, chain, path, tree, conditional
  extension    {thresholds, validation, inference} for a second stratum that extends the first: its rules run after
               the first stratum reaches its fixpoint and can't override it, so the policy's answers contain the
               first stratum's answers. Extension-derived facts are labelled "extension", never "core".

Not exposed, because the engine can't enforce them yet: evidence classes (held-out evidence is not yet a class),
independent-source validation (Investigation V).
"""
import copy
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from .errors import EgmError


class PolicyError(EgmError, ValueError):
    """An invalid policy configuration, or a policy operation that isn't allowed (unknown name, changing a built-in)."""


SHAPES = ("inverse", "chain", "path", "tree", "conditional")

# field -> (kind, default, engine key). Defaults admit everything the engine accepted: a field only restricts.
THRESHOLDS = {
    "minSampleSize": ("count", 0, "minSampleSize"), "minSupport": ("count", 0, "minSupport"),
    "minAgreement": ("share", 0.0, "minAgreement"), "minReliability": ("share", 0.0, "minReliability"),
    "minCoverage": ("share", 0.0, "minCoverage"), "minZ": ("number", None, "minZ"),
    "minLift": ("nonneg", 0.0, "minLift"), "maxUnknownShare": ("share", 1.0, "maxUnknownShare"),
    "minAgreementToCoverage": ("nonneg", 0.0, "minAgreementToCoverage"),
    # Round 2 W1a: coverage from a source rule whose own agreement is below this is not used (reliability falls back
    # to the rate, as with no estimate). 0 = off. Experimental.
    "minCoverageSourceAgreement": ("share", 0.0, "minCoverageSourceAgreement"),
}
VALIDATION = {"required": ("bool", False, "replication"), "method": ("method", "internal_replication", None),
              "split": ("split", "hash", "split"), "minPerHalf": ("count", 5, "minPerHalf"),
              "onInsufficient": ("insufficient", "reject", "onInsufficient")}
INFERENCE = {"maxDepth": ("count", 4, "maxDepth"), "shapes": ("shapes", list(SHAPES), "shapes")}
SECTIONS = {"thresholds": THRESHOLDS, "validation": VALIDATION, "inference": INFERENCE}
METHODS = {"internal_replication": "internal_replication", "split_half": "internal_replication"}
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _check(section, key, kind, v):
    where = f"{section}.{key}"
    if kind == "count":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0 or v != int(v):
            raise PolicyError(f"{where} must be a whole number >= 0, got {v!r}")
        return int(v)
    if kind == "share":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 1:
            raise PolicyError(f"{where} must be a number from 0 to 1, got {v!r}")
        return float(v)
    if kind == "nonneg":
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise PolicyError(f"{where} must be a number >= 0, got {v!r}")
        return float(v)
    if kind == "number":
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise PolicyError(f"{where} must be a number, got {v!r}")
        return float(v)
    if kind == "bool":
        if not isinstance(v, bool):
            raise PolicyError(f"{where} must be true or false, got {v!r}")
        return v
    if kind == "method":
        if v == "independent_sources":
            raise PolicyError(f"{where}: independent-source validation is not available yet (Investigation V); "
                              f"use internal_replication")
        if v not in METHODS:
            raise PolicyError(f"{where} must be one of {sorted(METHODS)}, got {v!r}")
        return METHODS[v]
    if kind == "insufficient":
        if v not in ("reject", "admit"):
            raise PolicyError(f"{where} must be 'reject' or 'admit', got {v!r}")
        return v
    if kind == "split":
        if v not in ("hash", "blocked"):
            raise PolicyError(f"{where} must be 'hash' or 'blocked', got {v!r}")
        return v
    if kind == "shapes":
        if isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        if not isinstance(v, (list, tuple)) or any(x not in SHAPES for x in v):
            raise PolicyError(f"{where} must be a list drawn from {list(SHAPES)}, got {v!r}")
        return [s for s in SHAPES if s in v]
    raise AssertionError(kind)


def _stratum(cfg, where):
    """Validate one stratum ({thresholds, validation, inference}); returns it complete, with defaults filled in."""
    if not isinstance(cfg, dict):
        raise PolicyError(f"{where} must be an object")
    unknown = set(cfg) - set(SECTIONS)
    if unknown:
        raise PolicyError(f"{where}: unknown section(s) {sorted(unknown)}; allowed: {sorted(SECTIONS)}")
    out = {}
    for sec, spec in SECTIONS.items():
        given = cfg.get(sec) or {}
        if not isinstance(given, dict):
            raise PolicyError(f"{where}.{sec} must be an object")
        bad = set(given) - set(spec)
        if bad:
            label = sec if where == "policy" else f"{where}.{sec}"
            raise PolicyError(f"{label}: unknown field(s) {sorted(bad)}; allowed: {sorted(spec)}")
        out[sec] = {k: _check(f"{where}.{sec}" if where != "policy" else sec, k, kind, given.get(k, copy.deepcopy(d)))
                    for k, (kind, d, _) in spec.items()}
    return out


def _engine_args(prefix, st):
    a = []
    for sec, spec in SECTIONS.items():
        for k, (kind, _, ek) in spec.items():
            v = st[sec][k]
            if ek is None or v is None:
                continue
            if kind == "bool":
                v = "true" if v else "false"
            elif kind == "shapes":
                v = ",".join(v) if v else ""
                if not v:
                    raise PolicyError("inference.shapes can't be empty: no rule could be admitted")
            a.append(f"{prefix}.{ek}={v}")
    return a


@dataclass
class Policy:
    """A validated policy version. ``id`` = name@version identifies it in every result."""
    name: str
    version: Union[int, str]
    thresholds: Dict = field(default_factory=dict)
    validation: Dict = field(default_factory=dict)
    inference: Dict = field(default_factory=dict)
    extension: Optional[Dict] = None
    description: str = ""
    builtin: bool = False
    created: str = ""

    @property
    def id(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def is_legacy(self) -> bool:
        return self.builtin and self.name == "legacy"

    def config(self) -> dict:
        """The configuration alone (what export writes, minus name and version)."""
        d = {"thresholds": self.thresholds, "validation": self.validation, "inference": self.inference}
        if self.extension is not None:
            d["extension"] = self.extension
        return copy.deepcopy(d)

    def to_dict(self) -> dict:
        d = {"name": self.name, "version": self.version, "description": self.description, "builtin": self.builtin,
             "created": self.created}
        d.update(self.config())
        return d

    def engine_command(self) -> str:
        """The single engine command that applies this policy (POLICY APPLY), or POLICY LEGACY."""
        if self.is_legacy:
            return "POLICY LEGACY"
        core = {"thresholds": self.thresholds, "validation": self.validation, "inference": self.inference}
        args = _engine_args("core", core) + (_engine_args("extension", self.extension) if self.extension else [])
        return f"POLICY APPLY {self.name} {self.version} " + " ".join(args)


def validate(cfg: dict) -> dict:
    """Validate a policy configuration ({thresholds, validation, inference, extension?}); return it complete.
    Raises PolicyError, naming the field, on anything unknown or out of range."""
    if not isinstance(cfg, dict):
        raise PolicyError("a policy configuration must be an object")
    allowed = set(SECTIONS) | {"extension"}
    unknown = set(cfg) - allowed
    if unknown:
        raise PolicyError(f"unknown policy section(s) {sorted(unknown)}; allowed: {sorted(allowed)}")
    out = _stratum({k: v for k, v in cfg.items() if k in SECTIONS}, "policy")
    if cfg.get("extension") is not None:
        out["extension"] = _stratum(cfg["extension"], "extension")
    for st, where in ((out, "policy"), (out.get("extension"), "extension")):
        if st and not st["inference"]["shapes"]:
            raise PolicyError(f"{where}: inference.shapes can't be empty (no rule could be admitted)")
    return out


def _merge(base: dict, change: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (change or {}).items():
        if k == "extension" and v is None:
            out.pop("extension", None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _builtin(name, cfg, description):
    c = validate(cfg)
    return Policy(name, "builtin-1", c["thresholds"], c["validation"], c["inference"], c.get("extension"), description,
                  True, "")


# Built-in profiles. Development values (studies/evidence_policy/DEVELOPMENT.md): exploratory until confirmed.
_STRICT = {"thresholds": {"minSampleSize": 5, "minReliability": 0.95, "minAgreementToCoverage": 0.8},
           "validation": {"required": True, "method": "internal_replication", "split": "hash", "minPerHalf": 5,
                          "onInsufficient": "reject"},
           "inference": {"maxDepth": 4}}
BUILTINS = {
    "legacy": Policy("legacy", "builtin-1", {}, {}, {}, None,
                     "The engine's behaviour before policies, byte for byte. Has no configuration.", True, ""),
    "strict": _builtin("strict", _STRICT,
                       "Minimum evidence, acceptable agreement and internal split-half replication."),
    "tendency": _builtin("tendency", {**_STRICT, "extension": {"inference": {"maxDepth": 4}}},
                         "The strict stratum, extended by every accepted rule without replication. Answers contain "
                         "strict's answers."),
}


class PolicyRegistry:
    """Versioned policy store: one JSON file per version under ``path`` (default $EGM_POLICY_DIR or ~/.egm/policies).
    Versions are immutable: update writes a new version, so a result naming name@version can always be reproduced."""

    def __init__(self, path: Optional[str] = None):
        self._path = path

    @property
    def path(self) -> str:
        return self._path or os.environ.get("EGM_POLICY_DIR") or os.path.join(os.path.expanduser("~"), ".egm", "policies")

    # --- reading ------------------------------------------------------------------------
    def _dir(self, name):
        return os.path.join(self.path, name)

    def versions(self, name: str) -> List[int]:
        if name in BUILTINS:
            return []
        d = self._dir(name)
        if not os.path.isdir(d):
            return []
        return sorted(int(f[1:-5]) for f in os.listdir(d) if re.fullmatch(r"v\d+\.json", f))

    def exists(self, name: str) -> bool:
        return name in BUILTINS or bool(self.versions(name))

    def get(self, ref: Union[str, Policy], version: Optional[int] = None) -> Policy:
        """A policy by name (latest version), "name@version", or a Policy (returned as is)."""
        if isinstance(ref, Policy):
            return ref
        name = ref
        if "@" in ref:
            name, v = ref.split("@", 1)
            if name in BUILTINS:
                if v != BUILTINS[name].version:
                    raise PolicyError(f"{name} is built-in; its only version is {BUILTINS[name].version}")
                return BUILTINS[name]
            try:
                version = int(v)
            except ValueError:
                raise PolicyError(f"bad version in {ref!r}") from None
        if name in BUILTINS:
            return BUILTINS[name]
        vs = self.versions(name)
        if not vs:
            raise PolicyError(f"no policy named {name!r}; available: {', '.join(p['name'] for p in self.list())}")
        v = vs[-1] if version is None else version
        if v not in vs:
            raise PolicyError(f"policy {name!r} has no version {v}; versions: {vs}")
        with open(os.path.join(self._dir(name), f"v{v}.json")) as f:
            d = json.load(f)
        c = validate({k: d[k] for k in ("thresholds", "validation", "inference", "extension") if k in d})
        return Policy(name, v, c["thresholds"], c["validation"], c["inference"], c.get("extension"),
                      d.get("description", ""), False, d.get("created", ""))

    def list(self) -> List[dict]:
        out = [{"name": n, "version": p.version, "builtin": True, "description": p.description} for n, p in BUILTINS.items()]
        if os.path.isdir(self.path):
            for n in sorted(os.listdir(self.path)):
                vs = self.versions(n)
                if vs:
                    out.append({"name": n, "version": vs[-1], "builtin": False, "versions": vs,
                                "description": self.get(n).description})
        return out

    # --- writing (never mutates an existing version) ------------------------------------
    def _write(self, name, cfg, description):
        c = validate(cfg)
        vs = self.versions(name); v = (vs[-1] + 1) if vs else 1
        os.makedirs(self._dir(name), exist_ok=True)
        d = {"name": name, "version": v, "description": description, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        d.update(c)
        path = os.path.join(self._dir(name), f"v{v}.json")
        with open(path + ".tmp", "w") as f:
            json.dump(d, f, indent=1)
        os.replace(path + ".tmp", path)
        return self.get(name, v)

    def _name_ok(self, name):
        if name in BUILTINS:
            raise PolicyError(f"{name!r} is a built-in policy and can't be changed; clone it to start a custom policy")
        if not NAME.match(name or ""):
            raise PolicyError(f"bad policy name {name!r}: letters, digits, '_', '.', '-'; at most 64; no '@'")

    def create(self, name: str, thresholds: Optional[dict] = None, validation: Optional[dict] = None,
               inference: Optional[dict] = None, extension: Optional[dict] = None, description: str = "") -> Policy:
        """A new policy (version 1). Unspecified fields take their defaults, which restrict nothing."""
        self._name_ok(name)
        if self.versions(name):
            raise PolicyError(f"policy {name!r} already exists (versions {self.versions(name)}); use update")
        cfg = {"thresholds": thresholds or {}, "validation": validation or {}, "inference": inference or {}}
        if extension is not None:
            cfg["extension"] = extension
        return self._write(name, cfg, description)

    def update(self, name: str, thresholds: Optional[dict] = None, validation: Optional[dict] = None,
               inference: Optional[dict] = None, extension: Union[dict, None, bool] = False,
               description: Optional[str] = None) -> Policy:
        """A new version: the latest version with these fields changed. ``extension=None`` removes the extension
        stratum; leaving it out keeps it."""
        self._name_ok(name)
        cur = self.get(name)
        change = {"thresholds": thresholds or {}, "validation": validation or {}, "inference": inference or {}}
        if extension is not False:
            change["extension"] = extension
        cfg = _merge(cur.config(), change)
        return self._write(name, cfg, cur.description if description is None else description)

    def clone(self, source: Union[str, Policy], name: str, description: Optional[str] = None) -> Policy:
        src = self.get(source)
        if src.is_legacy:
            raise PolicyError("legacy has no configuration to clone; clone strict or tendency instead")
        self._name_ok(name)
        if self.versions(name):
            raise PolicyError(f"policy {name!r} already exists")
        return self._write(name, src.config(), description if description is not None else f"cloned from {src.id}")

    def export(self, ref: Union[str, Policy], path: Optional[str] = None) -> dict:
        p = self.get(ref); d = p.to_dict()
        if path:
            with open(path, "w") as f:
                json.dump(d, f, indent=1)
        return d

    def import_(self, source: Union[str, dict], name: Optional[str] = None) -> Policy:
        """Import a configuration (a file path or a dict as export writes it). It becomes version 1 of a new policy, or
        the next version of an existing one with that name."""
        d = source
        if isinstance(source, str):
            with open(source) as f:
                d = json.load(f)
        if not isinstance(d, dict):
            raise PolicyError("an imported policy must be a JSON object")
        name = name or d.get("name")
        if not name:
            raise PolicyError("the imported policy has no name; pass name=")
        self._name_ok(name)
        meta = {"name", "version", "description", "builtin", "created"}
        cfg = {k: v for k, v in d.items() if k not in meta}
        return self._write(name, cfg, d.get("description", ""))


policies = PolicyRegistry()
