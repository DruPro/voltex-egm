"""Builds the agent lab. Hidden: world truth + answer key (agentlab/hidden). Visible to agents: one env dir per condition.
World: blind-world generator, scale 4 (2,000 individuals), seed 0, 50% coverage, 3% wrong facts, 1% contradictions."""
import sys, os, json, random, shutil, subprocess, collections, stat
sys.path.insert(0, "/home/claude/work/blind/hidden"); sys.path.insert(0, "/home/claude/work/blind")
from world import generate, observe
from lib import oracle
LAB = "/home/claude/work/agentlab"; HID = f"{LAB}/hidden"; os.makedirs(HID, exist_ok=True)
VOLTEX = "/home/claude/work/v21/voltex2"
T, E = generate(0, 4)
lines, info = observe(T, E, 0, 0.5, n_unseen=100, n_sparse=200)
obs = {tuple(f) for f in info["observed"]}
truth = {p: set(map(tuple, v)) for p, v in T.items()}
od = oracle(list(obs))
r = random.Random(2026)
idx = lambda p: {a: b for a, b in truth[p]}
lives, loc, works, over = idx("lives in"), idx("is located in"), idx("works as"), idx("is overseen by")
stated = lambda p, a, b: (p, a, b) in obs
wrong_subjects = {w[1] for w in info["wrong"]}
people = [p for p in E["individual"] if p not in info["unseen"] and p not in wrong_subjects]
Q = []
def add(kind, question, answer, accept=None, note=""):
    Q.append({"id": f"q{len(Q) + 1:02d}", "type": kind, "question": question, "answer": answer, "accept": accept or [answer], "note": note})
# 1. direct lookup (stated)
for p in r.sample([p for p in people if stated("lives in", p, lives[p])], 6):
    add("1 direct lookup", f"Which settlement does {p} live in?", lives[p])
# 2. two-step: region not stated, derivable from stated home + stated settlement region
c2 = [p for p in people if stated("lives in", p, lives[p]) and stated("is located in", lives[p], loc[lives[p]]) and not stated("is from", p, loc[lives[p]])]
for p in r.sample(c2, 8): add("2 two-step derivation", f"Which region is {p} from?", loc[lives[p]])
# 3. ancestry yes/no: true but unstated (derivable), and false
anc = [(a, b) for a, b in truth["is ancestor of"] if not stated("is ancestor of", a, b) and ("is ancestor of", a, b) in od and a not in info["unseen"] and b not in info["unseen"]]
for a, b in r.sample(anc, 4): add("3 multi-step ancestry", f"Is {a} an ancestor of {b}? Answer yes, no, or unknown.", "yes")
gen0 = [p for p in people if not any(c == p for c, _ in truth["is child of"])]
neg = []
while len(neg) < 2:
    a, b = r.choice(gen0), r.choice(people)
    if (a, b) not in truth["is ancestor of"] and a != b: neg.append((a, b))
for a, b in neg: add("3 multi-step ancestry", f"Is {a} an ancestor of {b}? Answer yes, no, or unknown.", "no", accept=["no", "unknown"], note="true answer is no; a knowledge base cannot prove a negative, so unknown is also accepted")
# 4. membership: derivable from profession + profession's institution, not stated, no exception
c4 = [p for p in people if stated("works as", p, works[p]) and stated("is overseen by", works[p], over[works[p]])
      and not any(stated("is member of", p, i) for i in E["institution"]) and {i for a, i in truth["is member of"] if a == p} == {over[works[p]]}]
for p in r.sample(c4, 4): add("4 membership derivation", f"Which institution is {p} a member of?", over[works[p]])
# 5. unanswerable: never-ingested individuals
for p in r.sample(info["unseen"], 6):
    add("5 unanswerable", f"Which settlement does {p} live in? If the knowledge base cannot answer, say unknown.", "unknown", note=f"true answer {lives[p]} is not in the knowledge base")
# 6. claim verification: is-from claims for people whose region is derivable but unstated
c6 = [p for p in c2 if p not in {q['question'].split()[3] for q in Q}]
for i, p in enumerate(r.sample(c6, 6)):
    if i % 2 == 0: add("6 claim verification", f"Claim: {p} is from {loc[lives[p]]}. Answer supported, contradicted, or unknown.", "supported")
    else:
        bad = r.choice([g for g in E["region"] if g != loc[lives[p]]])
        add("6 claim verification", f"Claim: {p} is from {bad}. Answer supported, contradicted, or unknown.", "contradicted")
# 7. updates: person moves to a settlement whose region is stated; ask region after recording the move
c7 = [p for p in people if stated("lives in", p, lives[p]) and p not in {w for q in Q for w in q["question"].split()}]
for p in r.sample(c7, 4):
    s2 = r.choice([s for s in E["settlement"] if loc[s] != loc[lives[p]] and stated("is located in", s, loc[s])])
    add("7 update then derive", f"New information: {p} has moved and now lives in {s2} (no longer in {lives[p]}). Record this change in the knowledge base, then answer: which region is {p} from now?", loc[s2])
json.dump({"questions": Q, "world": {"seed": 0, "scale": 4, "coverage": 0.5, "facts": len(lines)}}, open(f"{HID}/answer_key.json", "w"), indent=1)
public = [{"id": q["id"], "question": q["question"]} for q in Q]
print(len(Q), "questions", collections.Counter(q["type"] for q in Q))

# ---------------- environments ----------------
SEARCH_TOOL = r'''#!/usr/bin/env python3
"""kb_search WORD [WORD...] : print up to 30 knowledge-base lines containing all words (whole words, case-insensitive)."""
import sys, os, re, time
here = os.path.dirname(os.path.abspath(__file__)); words = [w.lower() for w in sys.argv[1:]]
open(os.path.join(here, "tool_log.txt"), "a").write(f"{time.time():.3f}\tkb_search\t{' '.join(sys.argv[1:])}\n")
if not words: print("usage: kb_search WORD [WORD...]"); sys.exit(1)
pats = [re.compile(r"\b" + re.escape(w) + r"\b") for w in words]; hits = []
for fn in ("facts.txt", "notes.txt"):
    p = os.path.join(here, fn)
    if os.path.exists(p):
        for l in open(p):
            if all(pt.search(l.lower()) for pt in pats): hits.append(l.rstrip())
print("\n".join(hits[:30]) + (f"\n... {len(hits) - 30} more matches, add words to narrow" if len(hits) > 30 else "") if hits else "no matches")
'''
ADD_TOOL = r'''#!/usr/bin/env python3
"""kb_add "FACT SENTENCE" : append a fact to notes.txt (searched by kb_search)."""
import sys, os, time
here = os.path.dirname(os.path.abspath(__file__)); fact = " ".join(sys.argv[1:]).strip()
open(os.path.join(here, "tool_log.txt"), "a").write(f"{time.time():.3f}\tkb_add\t{fact}\n")
open(os.path.join(here, "notes.txt"), "a").write(fact + "\n"); print("added:", fact)
'''
VOLTEX_TOOL = r'''#!/usr/bin/env python3
"""voltex "COMMAND" : query or update the Voltex memory.
  ASK <pattern with ?>      e.g. voltex "ASK kiruki lives in ?"   (stated + inferred answers, with proofs)
  UPDATE <fact>             replace the subject's earlier value, e.g. voltex "UPDATE kiruki lives in sadobe"
  RETRACT <fact> | INGEST <fact> | RELATIONS | CONFLICTS"""
import sys, os, subprocess, time
here = os.path.dirname(os.path.abspath(__file__)); cmd = " ".join(sys.argv[1:]).strip()
open(os.path.join(here, "tool_log.txt"), "a").write(f"{time.time():.3f}\tvoltex\t{cmd}\n")
verb = cmd.split()[0].upper() if cmd else ""
if verb not in ("ASK", "UPDATE", "RETRACT", "INGEST", "RELATIONS", "CONFLICTS"):
    print(__doc__); sys.exit(1)
jpath = os.path.join(here, "journal.txt"); journal = open(jpath).read().splitlines() if os.path.exists(jpath) else []
out = subprocess.run([os.path.join(here, ".engine", "voltex2")], input="\n".join([f"LOAD {os.path.join(here, '.engine', 'base.vtx2')}"] + journal + ["FIND __mark__", cmd, "EXIT"]) + "\n",
                     capture_output=True, text=True).stdout
res = out.split("[FIND] not stored\n", 1)[-1].rstrip().splitlines()
if verb in ("UPDATE", "RETRACT", "INGEST"): open(jpath, "a").write(cmd + "\n")
limit = 40
print("\n".join(res[:limit]) + (f"\n... {len(res) - limit} more lines" if len(res) > limit else ""))
'''
def mk(path, text):
    open(path, "w").write(text); os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
for cond in ("sonnet_search", "haiku_search", "sonnet_voltex", "haiku_voltex", "scripted_voltex"):
    d = f"{LAB}/env_{cond}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    json.dump(public, open(f"{d}/questions.json", "w"), indent=1)
    if "search" in cond:
        open(f"{d}/facts.txt", "w").write("\n".join(lines) + "\n"); mk(f"{d}/kb_search", SEARCH_TOOL); mk(f"{d}/kb_add", ADD_TOOL)
    else:
        os.makedirs(f"{d}/.engine"); shutil.copy(VOLTEX, f"{d}/.engine/voltex2")
        open(f"/tmp/kb.txt", "w").write("\n".join(lines) + "\n")
        subprocess.run([VOLTEX], input=f"INGESTFILE /tmp/kb.txt\nSAVE {d}/.engine/base.vtx2\nEXIT\n", capture_output=True, text=True)
        mk(f"{d}/voltex", VOLTEX_TOOL)
print("environments ready")
