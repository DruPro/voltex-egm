"""EGM as an MCP server (Model Context Protocol, JSON-RPC 2.0 over stdio). Standard library only.

    egm mcp kb.vtx                 # read-only: ask, values, history, relations, conflicts, infer
    egm mcp kb.vtx --writable      # also observe, ingest, save
    egm mcp facts.txt              # a facts file works too (ingested at start)

Messages are newline-delimited JSON on stdin/stdout; logs go to stderr. Each tool result carries
JSON text (for any client) and the same object as structuredContent.
"""
import json
import os
import sys
import time
import traceback

from . import __version__
from .engine import Engine
from .errors import EgmError, RelationNotLearned

# Newest first. 2026-07-28 (stateless: no initialize, server/discover, resultType on every result) is not
# implemented yet; stdio clients that speak it fall back to the initialize handshake and one of these.
PROTOCOLS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]
FACT_FIELDS = ("fact", "subject", "relation", "object", "status", "flag", "tier", "score", "because", "rule", "source", "note")

_PATTERN = {"type": "string", "description": "A fact pattern with ? for the slot to fill, e.g. '? calls pkg__connect' "
                                               "or 'pkg__Client raises ?'. Names never contain spaces."}
_STRICT = {"type": "boolean", "default": True,
           "description": "true (default): only stated facts and law-tier inferences. false: also tendency-tier "
                          "inferences, which raise recall but can be wrong."}

READ_TOOLS = [
    {"name": "egm_ask",
     "description": "Query the knowledge base. Returns current facts, inferences with their proofs (because/rule), and, "
                    "if include_history is set, past values. Every fact is labelled stated, current or inferred. "
                    "If the relation is unknown, the result says which relations exist.",
     "inputSchema": {"type": "object", "properties": {"pattern": _PATTERN, "strict": _STRICT,
                     "include_history": {"type": "boolean", "default": False}}, "required": ["pattern"]}},
    {"name": "egm_values",
     "description": "Like egm_ask but returns only the names that fill the ? slot, sorted. Cheapest way to get a list "
                    "(callers, callees, modules, exceptions).",
     "inputSchema": {"type": "object", "properties": {"pattern": _PATTERN, "strict": _STRICT}, "required": ["pattern"]}},
    {"name": "egm_ask_many",
     "description": "Run several patterns in one call (up to 50). Returns values per pattern. Use for multi-step "
                    "questions, e.g. the callers of X and then the module of each caller.",
     "inputSchema": {"type": "object", "properties": {"patterns": {"type": "array", "items": _PATTERN, "maxItems": 50},
                     "strict": _STRICT}, "required": ["patterns"]}},
    {"name": "egm_history",
     "description": "Past values for a pattern: facts that held before a source changed, were corrected, superseded "
                    "or withdrawn, with when and per which source.",
     "inputSchema": {"type": "object", "properties": {"pattern": _PATTERN}, "required": ["pattern"]}},
    {"name": "egm_relations",
     "description": "What the knowledge base knows how to answer: learned relations with fact counts, and the rules it "
                    "accepted (with evidence and tier). Call this first if unsure what to ask.",
     "inputSchema": {"type": "object", "properties": {
         "include_rejected": {"type": "boolean", "default": False, "description": "also list candidate rules that failed"}}}},
    {"name": "egm_conflicts",
     "description": "Stated facts that the rules contradict, and facts on which sources disagree.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "egm_infer",
     "description": "Facts derived by the accepted rules, optionally only those of one relation (e.g. 'imports').",
     "inputSchema": {"type": "object", "properties": {"relation": {"type": "string"},
                     "limit": {"type": "integer", "default": 100, "minimum": 1, "maximum": 2000}}}},
]
WRITE_TOOLS = [
    {"name": "egm_observe",
     "description": "Record what a source says now. scope 'snapshot' (default): facts is everything this record "
                    "states now, and facts it no longer states become history. scope 'partial': add facts only. "
                    "time and revision are integers that increase with each observation of a record.",
     "inputSchema": {"type": "object", "properties": {
         "source": {"type": "string", "description": "who says it, e.g. repo, docs, ticket (no spaces)"},
         "record": {"type": "string", "description": "which record of that source, e.g. a file path (no spaces)"},
         "time": {"type": "integer"}, "revision": {"type": "integer", "default": 1},
         "scope": {"type": "string", "enum": ["snapshot", "partial"], "default": "snapshot"},
         "facts": {"type": "array", "items": {"type": "string"}, "description": "'A relation B' lines"}},
         "required": ["source", "record", "time", "facts"]}},
    {"name": "egm_ingest",
     "description": "Add plain facts ('A relation B', no spaces inside names). A relation becomes queryable once it has "
                    "at least 3 facts with at least 2 different names in each slot.",
     "inputSchema": {"type": "object", "properties": {"facts": {"type": "array", "items": {"type": "string"}, "maxItems": 10000}},
                     "required": ["facts"]}},
    {"name": "egm_save",
     "description": "Save the knowledge base to the server's save path, so additions survive a restart.",
     "inputSchema": {"type": "object", "properties": {}}},
]
for t in READ_TOOLS:
    t["annotations"] = {"readOnlyHint": True, "openWorldHint": False}
for t in WRITE_TOOLS:
    t["annotations"] = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": t["name"] != "egm_observe",
                        "openWorldHint": False}


def _fact(f):
    d = f.to_dict()
    return {k: d[k] for k in FACT_FIELDS if d[k] not in ("", [], None)}


class Server:
    def __init__(self, kb_path, writable=False, save_path=None, settings=None, log=sys.stderr):
        self.kb_path, self.writable, self.log = kb_path, writable, log
        self.save_path = save_path or (kb_path[:-4] + ".vtx" if kb_path.endswith(".txt") else kb_path)
        self.engine = Engine.open(kb_path, settings=settings)
        self.engine.relations()             # build inferences now, so the first tool call is fast
        self.tools = READ_TOOLS + (WRITE_TOOLS if writable else [])
        self.names = {t["name"] for t in self.tools}
        self.dirty = False

    def _log(self, msg):
        print(f"[egm-mcp] {msg}", file=self.log, flush=True)

    # --- tools ---------------------------------------------------------------------------
    def _learned(self):
        return [r.relation for r in self.engine.relations()]

    def _unknown(self):
        return self.engine.unknown_note()   # not cached: added facts can change the vocabulary and so the cap

    def t_egm_ask(self, a):
        p = a["pattern"]; strict = a.get("strict", True)
        try:
            facts = self.engine.ask(p, require=True)
        except RelationNotLearned as e:
            return {"pattern": p, "facts": [], "note": str(e), "learned_relations": e.learned}
        hidden = 0
        out = []
        if strict:   # the engine-level strict policy (closed proofs), not a filter over the default answers
            kept = self.engine.ask(p, strict=True)
            keep = {(f.fact, f.status) for f in kept}
            hidden = sum(1 for f in facts if not f.is_history and (f.fact, f.status) not in keep)
            facts = kept + [f for f in facts if f.is_history]
        for f in facts:
            if f.is_history and not a.get("include_history", False):
                continue
            out.append(_fact(f))
        res = {"pattern": p, "strict": strict, "facts": out}
        if hidden:
            res["note"] = f"{hidden} answer(s) hidden by strict=true (tendency-tier inferences or stale facts); retry with strict=false to see them"
        if not out and not hidden:
            res["note"] = self._unknown()
        return res

    def t_egm_values(self, a):
        p = a["pattern"]
        try:
            self.engine.ask(p, require=True)
        except RelationNotLearned as e:
            return {"pattern": p, "values": [], "note": str(e), "learned_relations": e.learned}
        vals = self.engine.values(p, strict=a.get("strict", True))
        res = {"pattern": p, "strict": a.get("strict", True), "values": vals}
        if not vals: res["note"] = self._unknown()
        return res

    def t_egm_ask_many(self, a):
        ps = a["patterns"]
        if len(ps) > 50:
            raise ValueError("at most 50 patterns per call")
        return {"strict": a.get("strict", True),
                "results": [self.t_egm_values({"pattern": p, "strict": a.get("strict", True)}) for p in ps]}

    def t_egm_history(self, a):
        return {"pattern": a["pattern"], "history": [_fact(f) for f in self.engine.history(a["pattern"])]}

    def t_egm_relations(self, a):
        exp = self.engine.experimental()
        return {**({"experimental_settings": exp} if exp else {}),
                "relations": [{"template": r.template, "facts": r.facts} for r in self.engine.relations()],
                "rules": [{"rule": r.text, "accepted": r.accepted, "tier": r.tier, "rate": r.rate, "lift": r.lift,
                           "chains_seen": r.n, "conclusion_stated": r.k, "shape": r.shape, "premises": r.premises,
                           **({"condition": r.condition} if r.condition else {})}
                          for r in self.engine.rules(include_rejected=a.get("include_rejected", False))]}

    def t_egm_conflicts(self, a):
        return {"conflicts": [c.to_dict() for c in self.engine.conflicts()]}

    def t_egm_infer(self, a):
        rel, lim = a.get("relation"), int(a.get("limit", 100))
        facts = [f for f in self.engine.infer_all() if not rel or f.relation == rel]
        return {"total": len(facts), "facts": [{"fact": f.fact, "tier": f.tier} for f in facts[:lim]],
                "truncated": len(facts) > lim}

    def t_egm_observe(self, a):
        self.engine.observe(a["source"], a["record"], a["time"], a.get("revision", 1), a.get("scope", "snapshot"), a["facts"])
        self.dirty = True
        return {"observed": len(a["facts"]), "source": a["source"], "record": a["record"], "saved": False}

    def t_egm_ingest(self, a):
        n = self.engine.ingest_many(a["facts"]); self.dirty = True
        return {"ingested": n, "saved": False}

    def t_egm_save(self, a):
        self.engine.save(self.save_path); self.dirty = False
        return {"saved": self.save_path}

    # --- protocol ------------------------------------------------------------------------
    def handle(self, msg):
        """One JSON-RPC message in; a response dict out, or None for notifications."""
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        is_note = "id" not in msg
        try:
            if method == "initialize":
                want = params.get("protocolVersion")
                ver = want if want in PROTOCOLS else PROTOCOLS[0]
                self._log(f"client {params.get('clientInfo', {}).get('name', '?')} asked for protocol {want}; using {ver}")
                return self._ok(mid, {
                    "protocolVersion": ver,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "egm", "title": "EGM knowledge base", "version": __version__},
                    "instructions": (
                        "EGM answers questions about a fixed set of facts ('A relation B') and what follows from them, "
                        "with a proof for every inference. Call egm_relations first to see what can be asked. "
                        "Prefer strict=true (the default): it returns only stated facts and law-tier inferences. "
                        "Answers labelled 'stated' come from the source; 'inferred' answers come with their proof.")})
            if method in ("notifications/initialized", "notifications/cancelled"):
                return None
            if method == "ping":
                return self._ok(mid, {})
            if method == "tools/list":
                return self._ok(mid, {"tools": self.tools})
            if method == "tools/call":
                name, args = params.get("name"), params.get("arguments") or {}
                if name not in self.names:
                    hint = " (start the server with --writable to enable it)" if any(t["name"] == name for t in WRITE_TOOLS) else ""
                    return self._err(mid, -32602, f"unknown tool: {name}{hint}")
                t0 = time.perf_counter()
                try:
                    res = getattr(self, "t_" + name)(args)
                    err = False
                except (EgmError, ValueError, KeyError) as e:
                    res, err = {"error": f"{type(e).__name__}: {e}"}, True
                self._log(f"{name} {json.dumps(args)[:200]} -> {'error' if err else 'ok'} {1000 * (time.perf_counter() - t0):.1f} ms")
                return self._ok(mid, {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}],
                                      "structuredContent": res, "isError": err})
            if method in ("resources/list", "prompts/list"):
                return self._ok(mid, {method.split("/")[0]: []})
            if is_note:
                return None
            return self._err(mid, -32601, f"method not found: {method}")
        except Exception as e:  # never let one bad request kill the server
            self._log("internal error: " + traceback.format_exc())
            return None if is_note else self._err(mid, -32603, f"internal error: {e}")

    @staticmethod
    def _ok(mid, result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    @staticmethod
    def _err(mid, code, message):
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    def serve(self, stdin=sys.stdin, stdout=sys.stdout):
        self._log(f"serving {self.kb_path} ({'writable' if self.writable else 'read-only'}, {len(self.tools)} tools)")
        try:
            for line in stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError as e:
                    out = self._err(None, -32700, f"parse error: {e}")
                else:
                    if isinstance(msg, list):     # JSON-RPC batch (older protocol versions)
                        out = [r for r in (self.handle(m) for m in msg) if r is not None] or None
                    else:
                        out = self.handle(msg)
                if out is not None:
                    stdout.write(json.dumps(out, ensure_ascii=False) + "\n"); stdout.flush()
        finally:
            if self.dirty:
                self._log(f"unsaved additions discarded (call egm_save, or run with --autosave)"
                          if not getattr(self, "autosave", False) else f"autosaving to {self.save_path}")
                if getattr(self, "autosave", False):
                    self.engine.save(self.save_path)
            self.engine.close()


def run(kb, writable=False, save_path=None, autosave=False, settings=None):
    if not os.path.exists(kb):
        print(f"egm mcp: {kb}: no such file", file=sys.stderr); return 2
    s = Server(kb, writable=writable, save_path=save_path, settings=settings)
    s.autosave = autosave and writable
    s.serve()
    return 0
