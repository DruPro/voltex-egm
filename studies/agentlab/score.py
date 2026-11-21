"""Scores an answers.json against the hidden answer key. Usage: python3 score.py <env_dir> [...]"""
import json, sys, re, collections
key = {q["id"]: q for q in json.load(open("/home/claude/work/agentlab/hidden/answer_key.json"))["questions"]}
def norm(a): return re.sub(r"[^a-z0-9_ ]", " ", str(a).lower()).split()
def judge(q, ans):
    toks = norm(ans)
    acc = [a.lower() for a in q["accept"]]
    if toks and (" ".join(toks) in acc or toks[0] in acc): return "correct"
    if toks and toks[0] in ("unknown", "cannot", "not", "none", "insufficient", "no_answer"): return "abstained"
    return "wrong"
def score(env):
    ans = {a["id"]: a for a in json.load(open(f"{env}/answers.json"))}
    rows = []
    for qid, q in key.items():
        a = ans.get(qid, {}).get("answer", "")
        v = judge(q, a)
        rows.append({"id": qid, "type": q["type"], "expected": q["answer"], "given": a, "verdict": v})
    tools = collections.Counter(l.split("\t")[1] for l in open(f"{env}/tool_log.txt")) if __import__("os").path.exists(f"{env}/tool_log.txt") else {}
    by = collections.defaultdict(lambda: collections.Counter())
    for r in rows: by[r["type"]][r["verdict"]] += 1
    tot = collections.Counter(r["verdict"] for r in rows)
    # a "confident error" is a wrong answer that is not an abstention (hallucination-like)
    return {"env": env, "accuracy": tot["correct"] / len(rows), "correct": tot["correct"], "wrong": tot["wrong"], "abstained": tot["abstained"],
            "by_type": {k: dict(v) for k, v in sorted(by.items())}, "tool_calls": dict(tools), "rows": rows}
if __name__ == "__main__":
    for env in sys.argv[1:]:
        s = score(env); json.dump(s, open(f"{env}/score.json", "w"), indent=1)
        print(f"{env}: {s['correct']}/40 correct, {s['wrong']} wrong, {s['abstained']} abstained | tools {s['tool_calls']}")
        for k, v in s["by_type"].items(): print(f"   {k:26} {v}")
