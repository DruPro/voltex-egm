"""Verdicts H1-H6 from ../results/results.json (PREREGISTRATION.md).  python3 verdicts.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); R = json.load(open(os.path.join(HERE, "..", "results", "results.json")))
X1, X2, X3, X5 = R["X1"], R["X2"], R["X3"], R["X5"]
p2r = [x for x in X2 if x["program"].startswith("P2") and x["refresh"]][0]
p1r = [x for x in X2 if x["program"].startswith("P1") and x["refresh"]][0]
k = {x["K"]: x for x in X3}
def stops_at_first_undecidable(rows, need):
    first_unknown = next((i for i, x in enumerate(rows) if not x["law"]), None)
    first_need = next((i for i, x in enumerate(rows) if need(i, rows)), None)
    law_after = sum(1 for x in rows[first_unknown:] if x["law"]) if first_unknown is not None else None
    return first_unknown, first_need, law_after
# the step that needs a transition: step i uses (state before i, symbol i); state before i = truth of step i-1 (s0 at 0)
bits_mixed = None
v = {"H1": all(x["wrong"] == 0 and x["unknown"] == 0 and x["derived_stated"] == 0 and x["full_builds_first"] == 1
               and x["builds_after_first"] == 0 and x["output_rules_identical"] for x in X1),
     "H2": p2r["right"] == p2r["steps"] and p2r["full_builds"] == 0 and p2r["refresh_builds"] == p2r["steps"] - 1
           and p1r["right"] == p1r["steps"],
     "H3": p1r["full_builds"] == p1r["steps"] - 1 and p1r["ms_per_step"] >= 3 * p2r["ms_per_step"],
     "H4": all(k[a]["ms_per_step"] > k[b]["ms_per_step"] for a, b in ((1, 8), (8, 32), (32, 256)))
           and k[1]["ms_per_step"] >= 10 * k[256]["ms_per_step"],
     "H5": all(x["provenance"]["proof_reaches_stated"] == x["provenance"]["answers_checked"]
               and x["provenance"]["rules_with_examples"] == x["provenance"]["rules_used"]
               and x["provenance"]["support_count_matches_engine"] == x["provenance"]["rules_used"] for x in X1)}
wrong_law = {c: sum(1 for x in rows if x["law"] and x["law"] != [x["truth"]]) for c, rows in X5.items()}
first = {c: next((i for i, x in enumerate(rows) if not x["law"]), None) for c, rows in X5.items()}
after = {c: sum(1 for x in rows[first[c]:] if x["law"]) for c, rows in X5.items()}
# (b): the first step that needs (s1, b1) is the first step whose previous true state is s1 and whose truth came
# from b1; recomputed from the stored truth column: prev s1 and next s2 or s0 differ from the clean table's s2
rows = X5["b_mixed_transition"]; prev = "s0"; need_b = None
for i, x in enumerate(rows):
    if prev == "s1" and x["truth"] == "s2": need_b = i; break   # clean table: (s1, b1) -> s2
    prev = x["truth"]
v["H6"] = all(n == 0 for n in wrong_law.values()) and first["a_untaught_symbol"] == 12 and first["c_untaught_state"] == 0 \
    and first["b_mixed_transition"] == need_b and all(n == 0 for n in after.values())
out = {k2: "pass" if x else "fail" for k2, x in v.items()}
detail = {"x5_wrong_law": wrong_law, "x5_first_without_law": first, "x5_law_answers_after_first_unknown": after,
          "x5_b_first_step_needing_mixed_transition": need_b,
          "x3_ms_per_step": {K: k[K]["ms_per_step"] for K in k}, "x3_ratio_K1_K256": round(k[1]["ms_per_step"] / k[256]["ms_per_step"], 2),
          "x2_ms_per_step": {f"{x['program']} REFRESH {x['refresh']}": x["ms_per_step"] for x in X2}}
json.dump({"verdicts": out, "detail": detail}, open(os.path.join(HERE, "..", "results", "verdicts.json"), "w"), indent=1)
print(out); print(json.dumps(detail, indent=1))
