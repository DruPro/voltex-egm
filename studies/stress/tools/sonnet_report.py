"""Render the recorded Sonnet sessions (../sonnet/*.json) as a page (../sonnet/index.html) and Markdown
(docs/AGENT_SESSIONS.md). Transcript content is copied from the recordings; only the checks in CHECKS are written by
hand, from the hidden key and full facts (see sonnet_sessions.py)."""
import html, json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); SON = os.path.join(STUDY, "sonnet")

ORDER = ["t0_locate_default_maxwords", "t1_locate", "t2_impact", "t3_debug_exception", "t4_debug_kb"]
TITLES = {"t0_locate_default_maxwords": "0. Code navigation, first attempt: the engine was misconfigured",
          "t1_locate": "1. Code navigation: where does this function live?",
          "t2_impact": "2. Impact analysis before a refactor",
          "t3_debug_exception": "3. Debugging: where can this exception come from?",
          "t4_debug_kb": "4. Debugging the knowledge itself: a million suspicious facts"}
CHECKS = {
    "t0_locate_default_maxwords": [
        ("wheel WheelFile.writestr → wheel.wheelfile, inferred", "right (hidden fact)"),
        ("numpy and cloud-init: \"not in the knowledge base\"", "wrong, but honest: the engine ran with MAXWORDS 12,000 on a 40,918-word vocabulary, so stated facts about rarer names returned nothing and no warning reached Sonnet"),
        ("declined to guess from the names", "right call: it said a guess would come from its own memory, not the knowledge base")],
    "t1_locate": [
        ("numpy _block_slicing → numpy._core.shape_base", "right (hidden fact, recovered by inference)"),
        ("cloud-init read_seeded → cloudinit.util", "right (hidden fact)"),
        ("wheel WheelFile.writestr → wheel.wheelfile", "right (hidden fact)"),
        ("labelled all three inferred, tendency tier, moderate confidence", "right: none was stated")],
    "t2_impact": [
        ("3 direct callers", "right: 3 of 3, none missed"),
        ("3 second-level callers", "right: 3 of 3, none missed"),
        ("modules of the 6 callers", "right: 6 of 6, two of them inferred from hidden facts and flagged as such"),
        ("read_conf_from_cmdline has no callers", "right in the full facts; it suggested grepping before calling it dead code")],
    "t3_debug_exception": [
        ("subp and find_home raise it (stated)", "right"),
        ("4 callers of subp", "right: 4 of 4"),
        ("7 functions inferred to raise it because they sit in the subp module", "1 of 7 right (raise_on_invalid_command, a hidden fact); Sonnet called these \"weak leads\". The rule rests on a name collision in the extractor (section below)"),
        ("missed create_swapfile (hidden, in another module)", "no path in the facts could reach it")],
    "t4_debug_kb": [
        ("root cause: recommends(a,b) ⇒ depends on(b,a), law tier at 12% agreement", "right: the same finding as the full-truth analysis in the stress report"),
        ("3cpio → accountsservice, libc6 → systemd-resolved, libidn2 ↔ dbus are false", "right: none is in the real transitive closure"),
        ("\"libc6 depends on libgcc-s1 is backwards\"", "wrong: Debian's libc6 does depend on libgcc-s1. It was a hidden fact the engine recovered correctly"),
        ("\"real Debian dependency chains don't loop\"", "wrong: libc6 and libgcc-s1 depend on each other"),
        ("three tool results were too large for the client (75k-595k characters)", "an MCP server gap: egm_conflicts and egm_ask have no size limit")],
}
LESSONS = [
    ("The engine gives the model proofs, not just answers.", "In every session Sonnet quoted the premises and the rule, said which facts were stated and which inferred, and set its confidence from the rule's tier and rate. A developer can check an answer in seconds."),
    ("Strict mode is the right default.", "Sonnet always asked strict first, saw empty or partial results, and retried with strict off only when it needed tendencies, saying so in the answer."),
    ("The model stays honest when the engine is silent.", "In the misconfigured run (0) it refused to guess module names from memory. Silence is only safe if the engine explains it, which it didn't."),
    ("Debugging the knowledge base works like debugging code.", "Given only the tools, Sonnet traced a million-fact flood to one reversed rule in 22 engine calls and 100 s. The model's own claims still need checking: it called a true dependency a bug."),
    ("Sessions surface engine and tooling defects quickly.", "Four small sessions found three: the silent MAXWORDS cap, unbounded tool results, and an extractor name collision."),
]


def esc(s): return html.escape(str(s))


def load(t):
    p = os.path.join(SON, t + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def pretty_input(d):
    s = json.dumps(d, ensure_ascii=False)
    return s if len(s) < 400 else s[:400] + " …"


def pretty_result(s):
    s = s.strip()
    if s.startswith("Error: result"): return re.sub(r"Output has been saved to \S+", "Output was saved to a file.", s)[:300]
    try:
        d = json.loads(s)
        out = json.dumps(d, ensure_ascii=False)
        return out if len(out) < 500 else out[:500] + " …"
    except Exception:
        return s[:500] + (" …" if len(s) > 500 else "")


def md_session(r, t):
    m = r["meta"]; calls = [s for s in r["steps"] if s["kind"] == "tool_call" and s["tool"].startswith("mcp__egm__")]
    out = [f"## {TITLES[t]}", "", f"*Goal:* {r['goal']}  ", f"*Knowledge base:* `{r['kb']}`, settings `{' '.join(r['settings']) or 'defaults'}`  ",
           f"*Session:* {r['model']}, {len(calls)} engine calls, {m.get('num_turns')} turns, {m.get('wall_s')} s, ${(m.get('total_cost_usd') or 0):.2f}", "",
           "**Prompt**", "", "> " + r["prompt"].replace("\n", "\n> "), "", "**Tool calls** (results truncated)", ""]
    for s in r["steps"]:
        if s["kind"] == "tool_call" and s["tool"].startswith("mcp__egm__"):
            out.append(f"- `{s['tool'].replace('mcp__egm__', '')}` `{pretty_input(s['input'])}`")
        elif s["kind"] == "tool_result" and s["chars"] > 10 and out[-1].startswith("- `"):
            out.append(f"  - → {s['chars']:,} chars: `{pretty_result(s['result'])[:300]}`")
    out += ["", "**Sonnet's answer**", "", r["final"].strip(), "", "**Checked against the hidden key and full facts**", "",
            "| Claim | Verdict |", "|---|---|"] + [f"| {a} | {b} |" for a, b in CHECKS[t]] + [""]
    return "\n".join(out)


def mini_md(s):   # just enough Markdown for Sonnet's answers: headings, bold, code, lists, tables
    lines, out, i = s.strip().split("\n"), [], 0
    inl = lambda x: re.sub(r"`([^`]+)`", r"<code>\1</code>", re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", esc(x)))
    while i < len(lines):
        l = lines[i]
        if l.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|[\s\-:|]+\|$", lines[i]): rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            out.append("<div class='tw'><table>" + "".join("<tr>" + "".join(f"<{'th' if k == 0 else 'td'}>{inl(c)}</{'th' if k == 0 else 'td'}>" for c in r) + "</tr>" for k, r in enumerate(rows)) + "</table></div>")
            continue
        if l.startswith("#"): out.append(f"<h4>{inl(l.lstrip('#').strip())}</h4>")
        elif re.match(r"^\s*([-*]|\d+\.)\s", l):
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s", lines[i]):
                items.append(f"<li>{inl(re.sub(r'^\s*([-*]|\d+\.)\s', '', lines[i]))}</li>"); i += 1
            out.append("<ul>" + "".join(items) + "</ul>"); continue
        elif l.strip(): out.append(f"<p>{inl(l)}</p>")
        i += 1
    return "\n".join(out)


def html_session(r, t):
    m = r["meta"]; calls = [s for s in r["steps"] if s["kind"] == "tool_call" and s["tool"].startswith("mcp__egm__")]
    steps = []
    for s in r["steps"]:
        if s["kind"] == "tool_call" and s["tool"].startswith("mcp__egm__"):
            steps.append(f"<li class='call'><span class='tool'>{esc(s['tool'].replace('mcp__egm__', ''))}</span> <code>{esc(pretty_input(s['input']))}</code>")
        elif s["kind"] == "tool_result" and s["chars"] > 10 and steps and steps[-1].startswith("<li class='call'>"):
            steps[-1] += f"<div class='res'>→ {s['chars']:,} chars · <code>{esc(pretty_result(s['result']))}</code></div></li>"
    steps = [x if x.endswith("</li>") else x + "</li>" for x in steps]
    checks = "".join(f"<tr><td>{esc(a)}</td><td class='{'ok' if b.startswith('right') else 'no'}'>{esc(b)}</td></tr>" for a, b in CHECKS[t])
    return f"""<section class="session" id="{t}">
<h2>{esc(TITLES[t])}</h2>
<p class="meta">{esc(r['goal'])}<br>Knowledge base <code>{esc(r['kb'])}</code> · settings <code>{esc(' '.join(r['settings']) or 'defaults')}</code> · {esc(r['model'])} · {len(calls)} engine calls · {m.get('num_turns')} turns · {m.get('wall_s')} s · ${(m.get('total_cost_usd') or 0):.2f}</p>
<div class="prompt"><span class="lab">Prompt</span>{mini_md(r['prompt'])}</div>
<details><summary>Every engine call Sonnet made ({len(calls)})</summary><ol class="steps">{''.join(steps)}</ol></details>
<div class="answer"><span class="lab">Sonnet's answer</span>{mini_md(r['final'])}</div>
<div class="checks"><span class="lab">Checked against the hidden key and full facts</span><div class="tw"><table><tr><th>Claim</th><th>Verdict</th></tr>{checks}</table></div></div>
</section>"""


def main():
    rs = [(t, load(t)) for t in ORDER if load(t)]
    total = sum((r["meta"].get("total_cost_usd") or 0) for _, r in rs)
    intro = ("These are real, unedited sessions: Claude Sonnet 5.5 connected to a Voltex EGM knowledge base through `egm mcp`, "
             "with no shell, files or web, only the engine's tools. The knowledge bases are 64,763 facts from 125 installed "
             "Python packages and 14,296 facts about installed Debian packages. 20% of each was hidden from the engine, so "
             "the answers can be checked. Tool results are truncated for space; Sonnet's answers are complete.")
    md = ["# Sonnet working with Voltex EGM: recorded sessions", "", intro, "",
          f"Recorded {len(rs)} sessions, ${total:.2f} in total. Runner: `studies/stress/tools/sonnet_sessions.py`; recordings: `studies/stress/sonnet/*.json`.", "",
          "## What the sessions show", ""] + [f"- **{a}** {b}" for a, b in LESSONS] + [""]
    md += ["## Defects the sessions found", "",
           "- **A silent cap.** With `MAXWORDS` below the vocabulary, asking about a stated fact on a rarer name returns nothing, and neither `egm_relations` nor the empty result says why. Proposed: report `limits()` in `egm_relations` and add a note to empty results while a limit is active.",
           "- **Unbounded results.** `egm_conflicts` and `egm_ask` returned 75,000 to 595,000 characters, more than the client accepts. Proposed: a `limit` with a total count, as `egm_infer` already has.",
           "- **An extractor name collision.** `egm extract python` names a module `pkg__path` and a function `pkg__name`, so `cloudinit__subp` is both the module `subp.py` and its function `subp()`. 6 names collide this way and 62 facts read \"X is defined in X\". The learned rule \"defined in a module that raises E ⇒ raises E\" rests on them. (Fixed in the extractor since; these sessions used facts extracted before the fix.)", ""]
    md += [md_session(r, t) for t, r in rs]
    md += ["## How to run your own", "", "```", "egm mcp facts.txt --set MAXWORDS=50000      # size MAXWORDS to the vocabulary first",
           "claude mcp add egm -- egm mcp /abs/path/facts.txt", "```", "",
           "Then ask in plain language. Ask the model to separate stated from inferred facts and to show the proof; the tools return both.", ""]
    open(os.path.join(ROOT, "docs", "AGENT_SESSIONS.md"), "w").write("\n".join(md))

    lessons = "".join(f"<li><b>{esc(a)}</b> {esc(b)}</li>" for a, b in LESSONS)
    page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sonnet Sessions with Voltex EGM</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&family=Fraunces:opsz,wght@9..144,600&display=swap" rel="stylesheet">
<style>
:root {{ /* layout: one reading column; each session = prompt, collapsible calls, answer, verdict table */
 --bg:#f6f7f8; --surface:#ffffff; --ink:#15171a; --ink-2:#4b5159; --ink-3:#7c838c; --rule:#dde1e6; --accent:#3b5bdb; --ok:#1f7a3a; --no:#b3261e; --code:#eef1f5;
 --display:"Fraunces",Georgia,serif; --body:"IBM Plex Sans",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace; color-scheme:light; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#111317; --surface:#181b20; --ink:#eceef1; --ink-2:#b7bec8; --ink-3:#8a929c; --rule:#2b3038; --accent:#8ea4ff; --ok:#6fd08c; --no:#ff8a80; --code:#20242b; color-scheme:dark; }} }}
:root[data-theme="dark"] {{ --bg:#111317; --surface:#181b20; --ink:#eceef1; --ink-2:#b7bec8; --ink-3:#8a929c; --rule:#2b3038; --accent:#8ea4ff; --ok:#6fd08c; --no:#ff8a80; --code:#20242b; color-scheme:dark; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.6 var(--body); }}
main {{ max-width:880px; margin:0 auto; padding:40px 20px 80px; display:grid; gap:26px; }}
h1 {{ font:600 2rem/1.15 var(--display); margin:0; text-wrap:balance; }} h2 {{ font:600 1.3rem/1.3 var(--display); margin:0; text-wrap:balance; }}
h4 {{ margin:14px 0 4px; font-size:1rem; }} p, li {{ max-width:70ch; }} p {{ margin:6px 0; }}
.meta {{ color:var(--ink-3); font-size:.85rem; }} code {{ font-family:var(--mono); font-size:.84em; background:var(--code); padding:1px 4px; border-radius:3px; overflow-wrap:anywhere; }}
section {{ display:grid; gap:12px; }} .session {{ background:var(--surface); border:1px solid var(--rule); border-radius:10px; padding:20px; }}
.lab {{ display:block; font-size:.75rem; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-3); margin-bottom:4px; }}
.prompt {{ border-left:3px solid var(--rule); padding-left:12px; color:var(--ink-2); }}
.answer {{ border-left:3px solid var(--accent); padding-left:12px; }}
details summary {{ cursor:pointer; color:var(--accent); font-size:.9rem; }}
.steps {{ font-size:.82rem; padding-left:22px; display:grid; gap:8px; margin:10px 0 0; }} .steps li {{ max-width:none; }}
.tool {{ font-family:var(--mono); font-weight:500; }} .res {{ color:var(--ink-3); margin-top:2px; }}
.tw {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:.88rem; }} th, td {{ text-align:left; padding:6px 8px; border-bottom:1px solid var(--rule); vertical-align:top; }}
th {{ color:var(--ink-2); }} td.ok {{ color:var(--ok); }} td.no {{ color:var(--no); }}
ul {{ padding-left:20px; margin:6px 0; }} .lessons li {{ margin:6px 0; }}
a:focus-visible, summary:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
</style></head><body><main>
<header style="display:grid;gap:10px"><p class="meta">Voltex EGM · studies/stress · recorded 2026-11-21</p>
<h1>What it looks like when Sonnet works with Voltex EGM</h1><p>{esc(intro).replace('`egm mcp`', '<code>egm mcp</code>')}</p>
<p class="meta">{len(rs)} sessions, ${total:.2f} in total. Every claim was checked against the hidden facts; the verdicts are in the table under each answer.</p></header>
<section class="session"><h2>What the sessions show</h2><ul class="lessons">{lessons}</ul>
<h4>Defects the sessions found</h4><ul>
<li><b>A silent cap.</b> With <code>MAXWORDS</code> below the vocabulary, a question about a stated fact on a rarer name returns nothing, and nothing tells the model why (session 0).</li>
<li><b>Unbounded results.</b> <code>egm_conflicts</code> and <code>egm_ask</code> returned up to 595,000 characters, more than the client accepts (session 4).</li>
<li><b>An extractor name collision.</b> <code>cloudinit__subp</code> is both the module <code>subp.py</code> and its function <code>subp()</code>. 6 names collide, and 62 facts read "X is defined in X" (session 3).</li></ul></section>
{''.join(html_session(r, t) for t, r in rs)}
<section class="session"><h2>Run your own</h2><p>Size <code>MAXWORDS</code> to your vocabulary, serve the facts, and connect a client:</p>
<p><code>claude mcp add egm -- egm mcp /abs/path/facts.txt --set MAXWORDS=50000</code></p>
<p>Ask in plain language, and ask the model to separate stated from inferred facts and show the proof. The tools return both. <code>docs/BUILDING_A_LAYER.md</code> covers turning a codebase or table into facts.</p></section>
</main></body></html>"""
    open(os.path.join(SON, "index.html"), "w").write(page)
    print("wrote docs/AGENT_SESSIONS.md and studies/stress/sonnet/index.html")


if __name__ == "__main__":
    main()
