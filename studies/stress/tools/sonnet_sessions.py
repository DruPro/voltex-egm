"""Real Sonnet sessions against the engine over MCP (studies/stress). Exploratory; tasks fixed in TASKS before any run.

  python3 sonnet_sessions.py [TASK_ID ...]      runs claude -p with Sonnet, writes ../sonnet/<id>.json

Sonnet gets only the engine's MCP tools: no shell, no file reads, no web. It runs in an empty scratch directory, so it
can't read the source and every answer has to come from the engine. Each saved transcript keeps the prompt, every
tool call with its input and (truncated) result, Sonnet's text, the final answer, turns, time and cost. Machine paths
and session ids are removed. Answers are checked by hand against the hidden key (studies/stress/obs/keys) and the full facts.

Change after the first run (disclosed): t1 first ran with the default MAXWORDS (12,000) on a 40,918-word vocabulary.
Stated facts about rarer names then return nothing, and Sonnet answered "not in the knowledge base" for 2 of 3
(kept as ../sonnet/t0_locate_default_maxwords.json). The code tasks now set MAXWORDS=42000, as explore.py does.
"""
import json, os, re, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); OBS = os.path.join(STUDY, "obs"); OUT = os.path.join(STUDY, "sonnet")
MODEL = os.environ.get("SONNET_MODEL", "claude-sonnet-5-5")

TASKS = [
    {"id": "t1_locate", "kb": "code_realcode.txt", "set": ["COVERAGE=0", "MAXWORDS=42000"],
     "goal": "Code navigation: find where functions live when that fact was never stated (all three are in the hidden key).",
     "prompt": "You are helping a developer navigate a large Python codebase (125 installed packages). The facts about it are "
               "in the egm knowledge base, available through the egm tools; names look like package__module__function. "
               "Answer using only those tools:\n"
               "1. Which module is numpy's _block_slicing (numpy___block_slicing) defined in?\n"
               "2. Which module is cloud-init's read_seeded (cloudinit__read_seeded) defined in?\n"
               "3. Which module is wheel's WheelFile.writestr (wheel__WheelFile_writestr) defined in?\n"
               "For each, say whether the fact was stated or inferred, show the evidence chain, and how confident you are."},
    {"id": "t2_impact", "kb": "code_realcode.txt", "set": ["COVERAGE=0", "MAXWORDS=42000"],
     "goal": "Impact analysis before a refactor: direct and second-level callers.",
     "prompt": "I'm about to change the signature of cloud-init's load_yaml (cloudinit__load_yaml). Using only the egm tools, "
               "list every function that calls it directly, then every function that calls one of those callers. Group them "
               "by the module they are defined in where the knowledge base knows it, and flag anything you are unsure of."},
    {"id": "t3_debug_exception", "kb": "code_realcode.txt", "set": ["COVERAGE=0", "MAXWORDS=42000"],
     "goal": "Debugging: trace an exception to where it can be raised.",
     "prompt": "A cloud-init run crashed with ProcessExecutionError (cloudinit__ProcessExecutionError). Using only the egm "
               "tools, find which functions or modules can raise it, where those are defined, and which other functions call "
               "them, so I know where to start debugging. Separate what the knowledge base states from what it infers."},
    {"id": "t4_debug_kb", "kb": "world_packages.txt", "set": [],
     "goal": "Debugging the knowledge itself: why does the dpkg knowledge base derive over a million facts?",
     "prompt": "This egm knowledge base holds about 14,000 facts about installed Debian packages (depends on, recommends, "
               "section, priority, architecture, source). Inference derives over a million 'depends on' facts from them. "
               "Using only the egm tools, investigate whether the derived dependencies can be trusted and what causes the "
               "volume. Name the specific rules responsible, with their evidence, and recommend what to change."},
]


def mcp_config(task, td):
    args = ["-m", "egm.cli", "mcp", os.path.join(OBS, task["kb"])]
    for s in task["set"]: args += ["--set", s]
    cfg = {"mcpServers": {"egm": {"command": sys.executable, "args": args, "env": {"PYTHONPATH": ROOT}}}}
    p = os.path.join(td, "mcp.json"); json.dump(cfg, open(p, "w")); return p


def scrub(s):
    s = str(s).replace(ROOT, "<repo>").replace(os.path.expanduser("~"), "~")
    s = re.sub(r"~/\.claude/projects/[^\s\"\\]+", "<saved file>", s)
    return re.sub(r"/tmp/[^\s\"']+", "<tmp>", s)


def clean(events, task):
    steps, final, meta = [], None, {}
    for ev in events:
        t = ev.get("type")
        if t == "assistant":
            for c in ev["message"].get("content", []):
                if c.get("type") == "text" and c["text"].strip(): steps.append({"kind": "text", "text": scrub(c["text"])})
                elif c.get("type") == "tool_use": steps.append({"kind": "tool_call", "tool": c["name"], "input": c["input"]})
        elif t == "user":
            for c in ev["message"].get("content", []) if isinstance(ev["message"].get("content"), list) else []:
                if c.get("type") == "tool_result":
                    body = c.get("content"); body = body if isinstance(body, str) else " ".join(x.get("text", "") for x in body or [])
                    steps.append({"kind": "tool_result", "chars": len(body), "result": scrub(body[:3000])})
        elif t == "result":
            final = scrub(ev.get("result", ""))
            meta = {k: ev.get(k) for k in ("num_turns", "duration_ms", "total_cost_usd", "is_error")}
            meta["usage"] = {k: v for k, v in (ev.get("usage") or {}).items() if isinstance(v, int)}
    return {"task": task["id"], "goal": task["goal"], "model": MODEL, "kb": task["kb"], "settings": task["set"],
            "prompt": task["prompt"], "steps": steps, "final": final, "meta": meta}


def run(task):
    with tempfile.TemporaryDirectory() as td:
        cfg = mcp_config(task, td); work = os.path.join(td, "work"); os.makedirs(work)
        cmd = ["claude", "-p", task["prompt"], "--model", MODEL, "--mcp-config", cfg, "--strict-mcp-config",
               "--allowedTools", "mcp__egm__egm_relations,mcp__egm__egm_ask,mcp__egm__egm_values,mcp__egm__egm_ask_many,"
               "mcp__egm__egm_history,mcp__egm__egm_conflicts,mcp__egm__egm_infer",
               "--disallowedTools", "Bash,Read,Edit,Write,Grep,Glob,WebFetch,WebSearch,Task,Agent,NotebookEdit",
               "--output-format", "stream-json", "--verbose", "--no-session-persistence", "--max-turns", "30"]
        t = time.time()
        p = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=1800)
        events = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    r = clean(events, task); r["meta"]["wall_s"] = round(time.time() - t, 1); r["meta"]["exit"] = p.returncode
    if p.returncode and not events: r["stderr"] = scrub(p.stderr[-2000:])
    os.makedirs(OUT, exist_ok=True); json.dump(r, open(os.path.join(OUT, task["id"] + ".json"), "w"), indent=1)
    calls = sum(1 for s in r["steps"] if s["kind"] == "tool_call")
    print(f"{task['id']}: exit {p.returncode}, {calls} tool calls, {r['meta'].get('num_turns')} turns, "
          f"{r['meta'].get('wall_s')} s, ${r['meta'].get('total_cost_usd')}", flush=True)
    return r


if __name__ == "__main__":
    ids = sys.argv[1:] or [t["id"] for t in TASKS]
    for t in TASKS:
        if t["id"] in ids: run(t)
