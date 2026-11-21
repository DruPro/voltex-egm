"""Round 2 (pre-registered): set-valued and aggregate questions. Same world and knowledge base as round 1."""
import sys, os, json, random, shutil, subprocess, collections, stat
sys.path.insert(0, "/home/claude/work/blind/hidden"); sys.path.insert(0, "/home/claude/work/blind")
from world import generate, observe
from lib import oracle
LAB = "/home/claude/work/agentlab"; HID = f"{LAB}/hidden"
T, E = generate(0, 4); lines, info = observe(T, E, 0, 0.5, n_unseen=100, n_sparse=200)
obs = {tuple(f) for f in info["observed"]}
kb = obs | set(oracle(list(obs)))                       # what the knowledge base supports under the TRUE rules
truth = {(p, a, b) for p, fs in T.items() for a, b in fs}
def kbset(p, a=None, b=None): return sorted(x[2] if a else x[1] for x in kb if x[0] == p and (a is None or x[1] == a) and (b is None or x[2] == b))
def trset(p, a=None, b=None): return sorted(x[2] if a else x[1] for x in truth if x[0] == p and (a is None or x[1] == a) and (b is None or x[2] == b))
r = random.Random(77); Q = []
unseen = set(info["unseen"])
people = [p for p in E["individual"] if p not in unseen]
def add(kind, q, kb_ans, tr_ans):
    Q.append({"id": f"r{len(Q) + 1:02d}", "type": kind, "question": q, "kb_answer": kb_ans, "true_answer": tr_ans})
cand = [p for p in people if 4 <= len(kbset("is ancestor of", None, p)) <= 6]
for p in r.sample(cand, 5): add("A ancestors", f"List all ancestors of {p} (comma-separated names).", kbset("is ancestor of", None, p), trset("is ancestor of", None, p))
cand = [p for p in people if 3 <= len(kbset("is sibling of", p)) <= 8]
for p in r.sample(cand, 5): add("B siblings", f"List all siblings of {p} (comma-separated names).", kbset("is sibling of", p), trset("is sibling of", p))
regions = [g for g in E["region"] if 30 <= len(kbset("is from", None, g)) <= 60]
for g in r.sample(regions, 5): add("C region residents", f"List everyone who is from {g} (comma-separated names).", kbset("is from", None, g), trset("is from", None, g))
works_kb = {a: b for p, a, b in kb if p == "works as"}; works_tr = {a: b for p, a, b in truth if p == "works as"}
for g in r.sample(regions, 5):
    prof = r.choice(["farmer", "smith", "healer", "scribe", "merchant", "miner", "weaver", "guard"])
    kbn = sum(1 for x in kbset("is from", None, g) if works_kb.get(x) == prof); trn = sum(1 for x in trset("is from", None, g) if works_tr.get(x) == prof)
    add("D count join", f"How many people who are from {g} work as {prof}? Answer with a number.", kbn, trn)
json.dump({"questions": Q}, open(f"{HID}/answer_key_r2.json", "w"), indent=1)
print({q["id"]: (q["type"], len(q["kb_answer"]) if isinstance(q["kb_answer"], list) else q["kb_answer"]) for q in Q})
# environments: copy round-1 tools, add paging
for cond in ("sonnet_search", "haiku_search", "sonnet_voltex", "haiku_voltex", "scripted_voltex"):
    src, d = f"{LAB}/env_{cond}", f"{LAB}/r2_{cond}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    json.dump([{"id": q["id"], "question": q["question"]} for q in Q], open(f"{d}/questions.json", "w"), indent=1)
    if "search" in cond:
        shutil.copy(f"{src}/facts.txt", d)
        t = open(f"{src}/kb_search").read()
        t = t.replace('words = [w.lower() for w in sys.argv[1:]]', 'args = sys.argv[1:]; page = 1\nif "--page" in args: i = args.index("--page"); page = int(args[i + 1]); args = args[:i] + args[i + 2:]\nwords = [w.lower() for w in args]')
        t = t.replace('print("\\n".join(hits[:30]) + (f"\\n... {len(hits) - 30} more matches, add words to narrow" if len(hits) > 30 else "") if hits else "no matches")',
                      'sl = hits[(page - 1) * 30: page * 30]\nprint(("\\n".join(sl) + (f"\\n... {len(hits) - page * 30} more matches: use --page {page + 1}" if len(hits) > page * 30 else "")) if sl else "no matches")')
        t = t.replace('"""kb_search WORD [WORD...] :', '"""kb_search WORD [WORD...] [--page N] :')
        open(f"{d}/kb_search", "w").write(t); shutil.copy(f"{src}/kb_add", d)
    else:
        shutil.copytree(f"{src}/.engine", f"{d}/.engine")
        t = open(f"{src}/voltex").read()
        t = t.replace('cmd = " ".join(sys.argv[1:]).strip()', 'args = sys.argv[1:]; page = 1\nif len(args) >= 3 and args[-2].upper() == "PAGE": page = int(args[-1]); args = args[:-2]\ncmd = " ".join(args).strip()')
        t = t.replace('limit = 40\nprint("\\n".join(res[:limit]) + (f"\\n... {len(res) - limit} more lines" if len(res) > limit else ""))',
                      'limit = 40; sl = res[(page - 1) * limit: page * limit]\nprint("\\n".join(sl) + (f"\\n... {len(res) - page * limit} more lines: add PAGE {page + 1}" if len(res) > page * limit else ""))')
        open(f"{d}/voltex", "w").write(t)
    for f in os.listdir(d):
        p = os.path.join(d, f)
        if f in ("kb_search", "kb_add", "voltex"): os.chmod(p, 0o755)
print("round-2 environments ready")
