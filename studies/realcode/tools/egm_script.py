"""EGM-script: no LLM. Each question type maps to fixed EGM queries (one or two ASK steps) over facts.txt."""
import json, re, subprocess, sys
key = json.load(open(sys.argv[1])); facts = sys.argv[2]; V = "/home/claude/work/egm22/voltex2"
def ask(qs):
    script = f"INGESTFILE {facts}\n" + "".join(f"ASK {q}\nFIND __sep__\n" for q in qs) + "EXIT\n"
    out = subprocess.run([V], input=script, capture_output=True, text=True).stdout
    blocks = out.split("[FIND] not stored")[:len(qs)]
    res = []
    for b in blocks:
        vals = []
        for l in b.splitlines():
            m = re.match(r"^  (\S+) (is defined in|calls|raises|inherits from|imports) (\S+)\s+(stated|inferred)", l)
            if m: vals.append((m.group(1), m.group(3)))
        res.append(vals)
    return res
def tgt(q): return re.findall(r"`([^`]+)`", q["question"])[0]
answers = {}
for q in key:
    x = tgt(q); k = q["kind"]
    if k == "lookup": answers[q["id"]] = [b for a, b in ask([f"{x} is defined in ?"])[0]]
    elif k == "callers": answers[q["id"]] = sorted({a for a, b in ask([f"? calls {x}"])[0]})
    elif k == "caller_modules":
        cs = sorted({a for a, b in ask([f"? calls {x}"])[0]}); ms = ask([f"{c} is defined in ?" for c in cs]) if cs else []
        answers[q["id"]] = sorted({b for blk in ms for a, b in blk})
    elif k == "raises_1hop":
        own = {b for a, b in ask([f"{x} raises ?"])[0]}; cs = sorted({b for a, b in ask([f"{x} calls ?"])[0]})
        sub = ask([f"{c} raises ?" for c in cs]) if cs else []
        answers[q["id"]] = sorted(own | {b for blk in sub for a, b in blk})
    elif k == "grandparent":
        bs = sorted({b for a, b in ask([f"{x} inherits from ?"])[0]}); g = ask([f"{b} inherits from ?" for b in bs]) if bs else []
        answers[q["id"]] = sorted({b for blk in g for a, b in blk})
    elif k == "imports": answers[q["id"]] = sorted({b for a, b in ask([f"{x} imports ?"])[0]})
json.dump([{"id": k, "answer": v} for k, v in answers.items()], open(sys.argv[3], "w"), indent=0)
print(len(answers), "answers")
