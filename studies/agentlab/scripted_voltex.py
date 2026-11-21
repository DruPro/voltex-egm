"""Ceiling baseline with no LLM: each question is mapped by a fixed template to Voltex commands; the first answer is taken.
Uses only the public questions and the voltex tool in env_scripted_voltex."""
import json, subprocess, re, os
env = "/home/claude/work/agentlab/env_scripted_voltex"
qs = json.load(open(f"{env}/questions.json"))
def vx(cmd): return subprocess.run([f"{env}/voltex", cmd], capture_output=True, text=True).stdout
def first_obj(out, rel):
    for l in out.splitlines():
        m = re.match(rf"^\s+(\S+) {rel} (\S+)\s+(stated|inferred)", l)
        if m: return m.group(2)
    return "unknown"
answers = []
for q in qs:
    t = q["question"]
    if t.startswith("Which settlement does"): s = t.split()[3]; a = first_obj(vx(f"ASK {s} lives in ?"), "lives in")
    elif t.startswith("Which region is"): s = t.split()[3]; a = first_obj(vx(f"ASK {s} is from ?"), "is from")
    elif t.startswith("Which institution is"): s = t.split()[3]; a = first_obj(vx(f"ASK {s} is member of ?"), "is member of")
    elif t.startswith("Is "):
        x, y = t.split()[1], t.split()[5].rstrip("?")
        a = "yes" if re.search(rf"^\s+{x} is ancestor of {y}\s+(stated|inferred)", vx(f"ASK {x} is ancestor of ?"), re.M) else "unknown"
    elif t.startswith("Claim:"):
        s, g = t.split()[1], t.split()[4].rstrip(".")
        got = first_obj(vx(f"ASK {s} is from ?"), "is from")
        a = "unknown" if got == "unknown" else ("supported" if got == g else "contradicted")
    elif t.startswith("New information:"):
        s, s2 = t.split()[2], t.split()[9]
        vx(f"UPDATE {s} lives in {s2}"); a = first_obj(vx(f"ASK {s} is from ?"), "is from")
    else: a = "unknown"
    answers.append({"id": q["id"], "answer": a})
json.dump(answers, open(f"{env}/answers.json", "w"), indent=1)
