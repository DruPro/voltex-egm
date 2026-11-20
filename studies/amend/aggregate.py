import json, statistics as st, re, glob, sys
rows = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "results_amend.json"))
def m(xs): xs = [x for x in xs if x is not None]; return st.mean(xs) if xs else None
f = lambda x, d=3: "  n/a" if x is None else f"{x:.{d}f}"
variants = sorted({r["variant"] for r in rows}); rates = sorted({r["rate"] for r in rows})
print(f"{'rate':>5} {'variant':20} {'M1':>5} {'M2 stale':>8} {'M2b':>5} {'M3':>6} {'M3b':>6} {'M5':>5} {'true rules':>10} {'law acc':>7} {'decoys':>6} {'sec':>5}")
for rate in rates:
    for v in variants:
        R = [r for r in rows if r["rate"] == rate and r["variant"] == v]
        if not R: continue
        print(f"{rate:5.2f} {v:20} {f(m([r['M1'] for r in R]),2):>5} {f(m([r['M2'] for r in R])):>8} {f(m([r['M2b_derived_only'] for r in R]),2):>5} {f(m([r['M3'] for r in R]),4):>6} "
              f"{f(m([r['M3b'] for r in R]),4):>6} {f(m([r['M5'] for r in R]),2):>5} {m([r['true_rules'] for r in R]):10.1f} {m([r['law_rules_accepted'] for r in R]):7.1f} {m([r['decoys'] for r in R]):6.1f} {m([r['seconds'] for r in R]):5.1f}")
    print()
print("stale stated movers per rate (sum over seeds):", {rate: sum(r['stale_stated'] for r in rows if r['rate'] == rate and r['variant'] == variants[0]) for rate in rates})
