"""Round-2 scorer (pre-registered metrics). Set questions: precision / recall / F1 against the KB-supported answer
(and against the full hidden world). Count questions: exact match and absolute error."""
import json, sys, re, collections, os
key = {q["id"]: q for q in json.load(open("/home/claude/work/agentlab/hidden/answer_key_r2.json"))["questions"]}
def names(a): return {t for t in re.split(r"[,\s]+", str(a).lower().strip()) if t and t not in ("and", "unknown")}
def prf(got, want):
    got, want = set(got), set(want)
    if not got and not want: return 1, 1, 1
    p = len(got & want) / len(got) if got else 0; r = len(got & want) / len(want) if want else 0
    return p, r, (2 * p * r / (p + r) if p + r else 0)
def score(env):
    ans = {a["id"]: a.get("answer", "") for a in json.load(open(f"{env}/answers.json"))}
    rows = []
    for qid, q in key.items():
        a = ans.get(qid, "")
        if isinstance(q["kb_answer"], list):
            p, r, f = prf(names(a), q["kb_answer"]); pt, rt, ft = prf(names(a), q["true_answer"])
            rows.append({"id": qid, "type": q["type"], "n_given": len(names(a)), "n_kb": len(q["kb_answer"]), "P": p, "R": r, "F1": f, "F1_vs_world": ft})
        else:
            m = re.search(r"\d+", str(a)); v = int(m.group()) if m else None
            rows.append({"id": qid, "type": q["type"], "given": v, "kb": q["kb_answer"], "world": q["true_answer"],
                         "exact": v == q["kb_answer"], "abs_err": abs(v - q["kb_answer"]) if v is not None else None, "exact_vs_world": v == q["true_answer"]})
    sets = [r for r in rows if "F1" in r]; counts = [r for r in rows if "exact" in r]
    by = collections.defaultdict(list)
    for r in sets: by[r["type"]].append(r["F1"])
    tools = collections.Counter(l.split("\t")[1] for l in open(f"{env}/tool_log.txt")) if os.path.exists(f"{env}/tool_log.txt") else {}
    out = {"env": env, "mean_F1_sets": sum(r["F1"] for r in sets) / len(sets), "mean_P_sets": sum(r["P"] for r in sets) / len(sets),
           "mean_R_sets": sum(r["R"] for r in sets) / len(sets), "F1_by_type": {k: sum(v) / len(v) for k, v in sorted(by.items())},
           "counts_exact": sum(r["exact"] for r in counts), "counts_mean_abs_err": (lambda e: sum(e) / len(e) if e else None)([r["abs_err"] for r in counts if r["abs_err"] is not None]),
           "mean_F1_vs_world": sum(r["F1_vs_world"] for r in sets) / len(sets), "tool_calls": dict(tools), "rows": rows}
    return out
if __name__ == "__main__":
    for env in sys.argv[1:]:
        s = score(env); json.dump(s, open(f"{env}/score_r2.json", "w"), indent=1)
        print(f"{env}: mean F1 {s['mean_F1_sets']:.3f} (P {s['mean_P_sets']:.3f}, R {s['mean_R_sets']:.3f}) | by type "
              + ", ".join(f"{k} {v:.2f}" for k, v in s["F1_by_type"].items()) + f" | counts exact {s['counts_exact']}/5, mean abs err {s['counts_mean_abs_err']} | tools {s['tool_calls']}")
