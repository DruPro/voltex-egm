"""MCP server protocol tests (stdlib only).   python3 -m unittest tests/test_mcp.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EGM = os.path.join(ROOT, "bin", "egm")
M = os.path.join(ROOT, "examples", "tokenomics", "M.txt")
INIT = {"jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}


def session(msgs, *args, raw_lines=()):
    """Send messages to a fresh `egm mcp` and return the parsed replies (by id) and stderr."""
    lines = [json.dumps(m) for m in msgs] + list(raw_lines)
    r = subprocess.run([sys.executable, EGM, "mcp", *args], input="\n".join(lines) + "\n",
                       capture_output=True, text=True, timeout=60)
    out = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    return out, r.stderr


def call(i, name, args=None):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}


class TestProtocol(unittest.TestCase):
    def test_handshake_and_versions(self):
        for asked, got in (("2025-11-25", "2025-11-25"), ("2025-06-18", "2025-06-18"), ("2024-11-05", "2024-11-05"),
                           ("2099-01-01", "2025-11-25")):
            msg = dict(INIT, params=dict(INIT["params"], protocolVersion=asked))
            out, _ = session([msg], M)
            r = out[0]["result"]
            self.assertEqual(r["protocolVersion"], got)
            self.assertEqual(r["serverInfo"]["name"], "egm"); self.assertIn("tools", r["capabilities"])

    def test_notifications_get_no_reply(self):
        out, _ = session([INIT, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                          {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 9}},
                          {"jsonrpc": "2.0", "id": 1, "method": "ping"}], M)
        self.assertEqual([m["id"] for m in out], [0, 1]); self.assertEqual(out[1]["result"], {})

    def test_errors(self):
        out, _ = session([INIT, {"jsonrpc": "2.0", "id": 1, "method": "no/such"}, call(2, "egm_nope"),
                          call(3, "egm_observe", {"source": "s", "record": "r", "time": 1, "facts": []})], M,
                         raw_lines=["{not json"])
        by = {m["id"]: m for m in out}
        self.assertEqual(by[1]["error"]["code"], -32601)
        self.assertEqual(by[2]["error"]["code"], -32602)
        self.assertIn("--writable", by[3]["error"]["message"])
        self.assertEqual(by[None]["error"]["code"], -32700)

    def test_bad_arguments_are_tool_errors(self):
        out, _ = session([INIT, call(1, "egm_ask", {}), call(2, "egm_ask_many", {"patterns": ["a calls ?"] * 51})], M)
        for m in out[1:]:
            self.assertTrue(m["result"]["isError"]); self.assertIn("error", m["result"]["structuredContent"])

    def test_tools_list_is_deterministic_and_annotated(self):
        out, _ = session([INIT, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                          {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}], M)
        a, b = out[1]["result"]["tools"], out[2]["result"]["tools"]
        self.assertEqual(a, b)
        names = [t["name"] for t in a]
        self.assertEqual(names, ["egm_ask", "egm_values", "egm_ask_many", "egm_history", "egm_relations", "egm_conflicts", "egm_infer"])
        for t in a:
            self.assertTrue(t["annotations"]["readOnlyHint"]); self.assertEqual(t["inputSchema"]["type"], "object")


class TestTools(unittest.TestCase):
    def test_read_tools(self):
        out, err = session([INIT,
                            call(1, "egm_values", {"pattern": "? calls requests__select_proxy"}),
                            call(2, "egm_ask", {"pattern": "requests__sessions imports ?", "strict": False}),
                            call(3, "egm_ask", {"pattern": "requests__sessions imports ?"}),
                            call(4, "egm_ask", {"pattern": "x frobnicates ?"}),
                            call(5, "egm_relations"), call(6, "egm_conflicts"),
                            call(7, "egm_infer", {"relation": "imports", "limit": 3}),
                            call(8, "egm_ask_many", {"patterns": ["requests__Session_send calls ?", "requests__Session_send raises ?"]})], M)
        r = {m["id"]: m["result"]["structuredContent"] for m in out[1:]}
        for m in out[1:]:
            self.assertFalse(m["result"]["isError"])
            self.assertEqual(json.loads(m["result"]["content"][0]["text"]), m["result"]["structuredContent"])
        self.assertEqual(len(r[1]["values"]), 3)
        inf = [f for f in r[2]["facts"] if f["status"] == "inferred"]
        self.assertTrue(inf and inf[0]["because"] and inf[0]["tier"] == "tendency")
        self.assertTrue(all(f["status"] == "stated" for f in r[3]["facts"])); self.assertIn("hidden", r[3]["note"])
        self.assertIn("calls", r[4]["learned_relations"])
        self.assertEqual(len(r[5]["relations"]), 5); self.assertEqual(len(r[5]["rules"]), 3)
        self.assertEqual(r[6]["conflicts"], [])
        self.assertEqual(len(r[7]["facts"]), 3); self.assertTrue(r[7]["truncated"])
        self.assertEqual(len(r[8]["results"]), 2)
        self.assertIn("read-only", err)

    def test_empty_answer_says_unknown_and_names_the_cap(self):
        """An empty answer is reported as unknown, not false; under a MAXWORDS cap the note names the cap."""
        q = {"pattern": "requests__nosuchthing calls ?"}
        out, _ = session([INIT, call(1, "egm_ask", q), call(2, "egm_values", q)], M)
        for m in out[1:]:
            note = m["result"]["structuredContent"]["note"]
            self.assertIn("unknown, not false", note); self.assertNotIn("capped", note)
        out, _ = session([INIT, call(1, "egm_values", q)], M, "--set", "MAXWORDS=300")
        note = out[1]["result"]["structuredContent"]["note"]
        self.assertIn("unknown, not false", note); self.assertIn("capped", note); self.assertIn("MAXWORDS", note)

    def test_write_tools_and_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            save = os.path.join(td, "kb.vtx")
            facts1 = ["svc__a calls svc__db", "svc__b calls svc__db", "svc__c calls svc__cache"]
            facts2 = ["svc__a calls svc__cache", "svc__b calls svc__db", "svc__c calls svc__cache"]
            out, _ = session([INIT, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                              call(2, "egm_observe", {"source": "repo", "record": "svc.py", "time": 1, "facts": facts1}),
                              call(3, "egm_observe", {"source": "repo", "record": "svc.py", "time": 2, "facts": facts2}),
                              call(4, "egm_values", {"pattern": "svc__a calls ?"}),
                              call(5, "egm_history", {"pattern": "svc__a calls ?"}),
                              call(6, "egm_ingest", {"facts": ["x__p calls x__q"]}),
                              call(7, "egm_save"),
                              call(8, "egm_observe", {"source": "bad source", "record": "r", "time": 1, "facts": ["a b c"]})],
                             M, "--writable", "--save-to", save)
            by = {m["id"]: m["result"] for m in out}
            self.assertIn("egm_observe", [t["name"] for t in by[1]["tools"]])
            self.assertEqual(by[4]["structuredContent"]["values"], ["svc__cache"])
            self.assertEqual(by[5]["structuredContent"]["history"][0]["object"], "svc__db")
            self.assertEqual(by[6]["structuredContent"]["ingested"], 1)
            self.assertEqual(by[7]["structuredContent"]["saved"], save)
            self.assertTrue(by[8]["isError"])
            out, _ = session([INIT, call(1, "egm_values", {"pattern": "svc__a calls ?"})], save)
            self.assertEqual(out[1]["result"]["structuredContent"]["values"], ["svc__cache"])

    def test_unsaved_additions_warned_or_autosaved(self):
        with tempfile.TemporaryDirectory() as td:
            save = os.path.join(td, "kb.vtx")
            _, err = session([INIT, call(1, "egm_ingest", {"facts": ["a calls b"]})], M, "--writable", "--save-to", save)
            self.assertIn("unsaved additions discarded", err); self.assertFalse(os.path.exists(save))
            _, err = session([INIT, call(1, "egm_ingest", {"facts": ["a calls b"]})], M, "--writable", "--autosave", "--save-to", save)
            self.assertTrue(os.path.exists(save))


if __name__ == "__main__":
    unittest.main()
