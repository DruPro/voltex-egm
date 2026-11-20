"""Interop check: drive `egm mcp` with the official MCP Python client (pip install mcp).

    python tests/interop_mcp_client.py path/to/bin/egm examples/tokenomics/M.txt
Not part of `make test` (it needs the mcp package); run it with `make interop`.
"""
import asyncio
import json
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EGM, KB = sys.argv[1], sys.argv[2]


def g(obj, *names):
    """Field access across mcp client versions (camelCase in 1.x, snake_case in 2.x)."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    raise AttributeError(names[0])


def payload(r):
    sc = None
    for n in ("structured_content", "structuredContent"):
        sc = sc or getattr(r, n, None)
    return sc if sc else json.loads(r.content[0].text)


async def main():
    ok = []

    def check(name, cond):
        ok.append(bool(cond)); print(("  PASS  " if cond else "  FAIL  ") + name)

    params = StdioServerParameters(command=sys.executable, args=[EGM, "mcp", KB])
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        init = await s.initialize()
        info = g(init, "server_info", "serverInfo")
        check(f"initialize (protocol {g(init, 'protocol_version', 'protocolVersion')}, server {info.name} {info.version})",
              info.name == "egm")
        tools = {t.name for t in (await s.list_tools()).tools}
        check("read-only tools listed, write tools hidden", "egm_ask" in tools and "egm_observe" not in tools)
        res = payload(await s.call_tool("egm_values", {"pattern": "? calls requests__select_proxy"}))
        check("egm_values", len(res["values"]) == 3)
        res = payload(await s.call_tool("egm_ask", {"pattern": "requests__sessions imports ?", "strict": False}))
        inf = [f for f in res["facts"] if f["status"] == "inferred"]
        check("egm_ask returns inferences with proofs", inf and inf[0]["because"] and inf[0]["rule"])
        res = payload(await s.call_tool("egm_ask", {"pattern": "requests__sessions imports ?"}))
        check("egm_ask strict by default, says what it hid", all(f["status"] == "stated" for f in res["facts"]) and "hidden" in res.get("note", ""))
        res = payload(await s.call_tool("egm_ask", {"pattern": "x frobnicates ?"}))
        check("unknown relation explained", "calls" in res.get("learned_relations", []))
        res = payload(await s.call_tool("egm_ask_many", {"patterns": ["requests__Session_send calls ?", "requests__Session_send raises ?"]}))
        check("egm_ask_many", len(res["results"]) == 2 and res["results"][0]["values"])
        res = payload(await s.call_tool("egm_relations", {}))
        check("egm_relations", len(res["relations"]) == 5 and res["rules"])
        res = payload(await s.call_tool("egm_infer", {"relation": "imports", "limit": 5}))
        check("egm_infer", res["total"] > 0 and len(res["facts"]) == 5 and res["truncated"])
        res = await s.call_tool("egm_ask", {})
        check("missing argument is a tool error, not a crash", g(res, "is_error", "isError"))

    with tempfile.TemporaryDirectory() as td:
        save = f"{td}/kb.vtx"
        params = StdioServerParameters(command=sys.executable, args=[EGM, "mcp", KB, "--writable", "--save-to", save])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            check("--writable adds observe/ingest/save", {"egm_observe", "egm_ingest", "egm_save"} <= tools)
            facts = ["svc__a calls svc__db", "svc__b calls svc__db", "svc__c calls svc__cache"]
            await s.call_tool("egm_observe", {"source": "repo", "record": "svc.py", "time": 1, "facts": facts})
            await s.call_tool("egm_observe", {"source": "repo", "record": "svc.py", "time": 2,
                                              "facts": ["svc__a calls svc__cache", "svc__b calls svc__db", "svc__c calls svc__cache"]})
            now = payload(await s.call_tool("egm_values", {"pattern": "svc__a calls ?"}))
            past = payload(await s.call_tool("egm_history", {"pattern": "svc__a calls ?"}))
            check("observe: new value current, old value in history",
                  now["values"] == ["svc__cache"] and past["history"] and past["history"][0]["object"] == "svc__db")
            res = payload(await s.call_tool("egm_save", {}))
            check("egm_save", res["saved"] == save)
        params = StdioServerParameters(command=sys.executable, args=[EGM, "mcp", save])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            now = payload(await s.call_tool("egm_values", {"pattern": "svc__a calls ?"}))
            check("saved additions survive a restart", now["values"] == ["svc__cache"])

    print(f"\n{sum(ok)}/{len(ok)} passed")
    return 0 if all(ok) else 1


sys.exit(asyncio.run(main()))
