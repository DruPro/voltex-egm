import json, sys, statistics as st, collections
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "results_decl.json"))
R.setdefault("S1", [])
conds = sorted({r["cond"] for r in R["S2"]}, key=lambda c: ["A","B","C1","C2","C2fn"].index(c))
def tot(rows, pfx):
    c = collections.Counter()
    for r in rows:
        for k, v in r.items():
            if k.startswith(pfx) and isinstance(v, int): c[k[len(pfx):]] += v
    return c
def fmt(c, keys=("right", "wrong", "ambiguous", "abstain")):
    n = sum(c[k] for k in keys)
    return "n=%-4d " % n + " ".join(f"{k[:5]}={c[k] / n:.3f}" if n else f"{k[:5]}=  -  " for k in keys)
if R["S1"]: print("== S1 (pooled over seeds) ==")
for m, label in [("P1_", "P1 mover current residence"), ("P2_", "P2 stale stated is-from"), ("P3_", "P3 mover previous residence"),
                 ("P4from_", "P4 non-mover is-from"), ("P4lives_", "P4 non-mover lives-in"), ("P5_", "P5 settlement current region"),
                 ("P6_", "P6 settlement previous region"), ("P5r_stated_", "P5r residents, stated stale"), ("P5r_derived_", "P5r residents, derived only")]:
    print(label)
    for c in conds: print(f"   {c:3} {fmt(tot([r for r in R['S1'] if r['cond'] == c], m))}")
print("P5c stale inverse still asserted / region changes:", {c: (sum(r.get('P5c_stale_inverse_asserted', 0) for r in R['S1'] if r['cond'] == c), sum(r.get('P5c_n', 0) for r in R['S1'] if r['cond'] == c)) for c in conds})
for c in conds:
    rows = [r for r in R["S1"] if r["cond"] == c]
    print(f"{c:3} time mean {st.mean(r['seconds'] for r in rows):.2f}s  save bytes {st.mean(r['save_bytes'] for r in rows):.0f}  ops/records per event {sum(r['records_or_cmds'] for r in rows) / sum(r['events'] for r in rows):.2f}"
          f"  bytes per event {sum(r['bytes'] for r in rows) / sum(r['events'] for r in rows):.1f}  true rules {st.mean(r['true_rules'] for r in rows):.1f}  decoys {st.mean(r['decoys'] for r in rows):.1f}"
          f"  amend-vocab rules {sum(r['amend_vocab_rules'] for r in rows)}  amend-vocab relations {sum(r['amend_vocab_relations'] for r in rows)}  persist {sum(bool(r['persist_identical']) for r in rows)}/{len(rows)}")
print("\n== S2 (pooled over seeds) ==")
for sc in ["B1", "B2", "D1", "D2", "D3", "F1", "F2"]:
    print(sc)
    for c in conds:
        rows = [r for r in R["S2"] if r["cond"] == c]
        extra = ""
        if sc == "D3": extra = f"  one amendment recorded {sum(r.get('D3_one_amendment', 0) for r in rows)}/{sum(r.get('D3_n', 0) for r in rows)}"
        if sc == "F1": extra = f"  withdrawn amendment still visible {sum(r.get('F1_log_kept', 0) for r in rows)}/{sum(r.get('F1_n', 0) for r in rows)}"
        print(f"   {c:3} current {fmt(tot(rows, sc + '_cur_'))} | held {fmt(tot(rows, sc + '_held_'))}{extra}")
print("E (contradiction, no amendment)")
for c in conds:
    t = tot([r for r in R["S2"] if r["cond"] == c], "E_"); n = sum(t.values())
    print(f"   {c:3} " + " ".join(f"{k}={t[k] / n:.3f}" for k in ["flagged", "ambiguous_unflagged", "single_new", "single_old"]) + f"  n={n}")
print("S2 persistence:", {c: f"{sum(bool(r['persist_identical']) for r in R['S2'] if r['cond'] == c)}/5" for c in conds})
