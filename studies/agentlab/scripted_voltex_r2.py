"""Round-2 scripted Voltex (no LLM). Two variants from the same tool outputs: all answers, and law-labelled + stated only."""
import json, subprocess, re, os, shutil
env = "/home/claude/work/agentlab/r2_scripted_voltex"
qs = json.load(open(f"{env}/questions.json"))
def vx_all(cmd):
    lines, page = [], 1
    while True:
        out = subprocess.run([f"{env}/voltex", cmd, "PAGE", str(page)], capture_output=True, text=True).stdout.splitlines()
        more = any("more lines: add PAGE" in l for l in out)
        lines += [l for l in out if "more lines: add PAGE" not in l]
        if not more: return lines
        page += 1
def facts(lines, rel):
    res = []
    for l in lines:
        m = re.match(rf"^\s+(\S+) {rel} (\S+)\s+(stated|inferred)( \[(law|tendency)\])?", l)
        if m: res.append((m.group(1), m.group(2), "law" if m.group(3) == "stated" or m.group(5) == "law" else "tendency"))
    return res
ans_all, ans_law = [], []
for q in qs:
    t = q["question"]
    if t.startswith("List all ancestors of"):
        x = t.split()[4]; f = facts(vx_all(f"ASK ? is ancestor of {x}"), "is ancestor of"); a = [s for s, o, l in f]; b = [s for s, o, l in f if l == "law"]
    elif t.startswith("List all siblings of"):
        x = t.split()[4]; f = facts(vx_all(f"ASK {x} is sibling of ?"), "is sibling of"); a = [o for s, o, l in f]; b = [o for s, o, l in f if l == "law"]
    elif t.startswith("List everyone who is from"):
        g = t.split()[5]; f = facts(vx_all(f"ASK ? is from {g}"), "is from"); a = [s for s, o, l in f]; b = [s for s, o, l in f if l == "law"]
    else:
        g, prof = t.split()[6], t.split()[9].rstrip("?")
        f = facts(vx_all(f"ASK ? is from {g}"), "is from"); people_all = [s for s, o, l in f]; people_law = [s for s, o, l in f if l == "law"]
        works = {p: [o for s, o, l in facts(vx_all(f"ASK {p} works as ?"), "works as") if l == "law"] for p in people_all}
        a = [str(sum(1 for p in people_all if prof in works[p]))]; b = [str(sum(1 for p in people_law if prof in works[p]))]
    ans_all.append({"id": q["id"], "answer": ", ".join(a)}); ans_law.append({"id": q["id"], "answer": ", ".join(b)})
json.dump(ans_all, open(f"{env}/answers.json", "w"), indent=1)
d2 = env + "_lawonly"; shutil.rmtree(d2, ignore_errors=True); os.makedirs(d2); json.dump(ans_law, open(f"{d2}/answers.json", "w"), indent=1)
