"""Mean +- s.d. over 5 seeds for every system and coverage level, plus rule-level analysis."""
import json, statistics as st, collections
rows = json.load(open("results/main_runs.json"))
SYS = ["voltex_on", "voltex_off", "graph", "oracle"]
def ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return "n/a"
    return f"{st.mean(xs):.3f} ± {st.stdev(xs):.3f}" if len(xs) > 1 else f"{xs[0]:.3f}"
out = {}
lines = []
for cov in (0.3, 0.5, 0.7):
    R = [r for r in rows if r["coverage"] == cov]
    lines.append(f"\n=== coverage {int(cov * 100)}%  (n={len(R)} seeds, observations {ms([r['observations'] for r in R])})")
    lines.append(f"{'system':11} {'derived':>14} {'precision':>15} {'recall(all heldout)':>20} {'recall(derivable)':>18} {'FPR':>15} {'FNR':>15}")
    for s in SYS:
        g = lambda k: [r[s][k] for r in R]
        q = lambda k: [r[s]["questions"][k] for r in R]
        lines.append(f"{s:11} {ms(g('derived')):>14} {ms(g('precision')):>15} {ms(g('recall')):>20} {ms(g('recall_on_derivable')):>18} {ms(q('FPR')):>15} {ms(q('FNR')):>15}")
    lines.append("  recall by inference depth (voltex_on vs oracle):")
    depths = sorted({d for r in R for d in r["voltex_on"]["recall_by_depth"]})
    for d in depths:
        vo = [r["voltex_on"]["recall_by_depth"].get(d, {}).get("recall") for r in R]
        orc = [r["oracle"]["recall_by_depth"].get(d, {}).get("recall") for r in R]
        n = [r["voltex_on"]["recall_by_depth"].get(d, {}).get("heldout", 0) for r in R]
        lines.append(f"    depth {d:14} heldout {ms(n):>16}  voltex {ms(vo):>15}  oracle {ms(orc):>15}")
    v = [r["voltex_on"] for r in R]
    lines.append(f"  rules accepted {ms([x['rules']['accepted'] for x in v])}, valid {ms([x['rules']['valid(true_conf>=0.9)'] for x in v])}, "
                 f"rule precision {ms([x['rules']['rule_precision'] for x in v])}, designed true rules found {ms([len(x['rules']['designed_true_found']) for x in v])} of 13")
    lines.append(f"  contradictions: injected {ms([x['contradictions']['injected'] for x in v])}, flagged {ms([x['contradictions']['flagged'] for x in v])}, "
                 f"detection recall {ms([x['contradictions']['detection_recall'] for x in v])}, flag precision {ms([x['contradictions']['flag_precision'] for x in v])}")
    lines.append(f"  sparse entities (only 'lives in' + 'works as' ingested): heldout {ms([x['sparse_entities']['heldout'] for x in v])}, "
                 f"recovered {ms([x['sparse_entities']['recovered'] for x in v])}, wrong {ms([x['sparse_entities']['wrong'] for x in v])}")
    lines.append(f"  unseen entities: facts derived about them {ms([x['unseen_entities']['facts_about_them_derived'] for x in v])}")
    lat = [x["latency_ms"] for x in v]
    lines.append("  latency ms: " + ", ".join(f"{k} {ms([l[k] for l in lat])}" for k in lat[0]) + f" | RSS MB {ms([x['rss_mb'] for x in v])}")
# rule catalogue across all 15 runs
cat = collections.defaultdict(lambda: {"runs": 0, "by_cov": collections.Counter(), "true_conf": [], "agree": [], "rate": [], "designed": "", "n": []})
for r in rows:
    for x in r["voltex_on"]["rules"]["list"]:
        k = (x["type"], x["r1"], x["r2"] if x["type"] != "I" else None, x["r3"])
        c = cat[k]; c["runs"] += 1; c["by_cov"][int(r["coverage"] * 100)] += 1
        c["true_conf"].append(x["true_conf"]); c["agree"].append(x["agree"]); c["rate"].append(x["rate"]); c["n"].append(x["n"])
        c["designed"] = "designed-true" if x["designed_true"] else ("designed-decoy" if x["designed_decoy"] else "")
lines.append("\n=== every rule Voltex accepted in any run (15 runs) ===")
lines.append(f"{'rule':78} {'runs 30/50/70':>14} {'true conf':>9} {'agree':>6} {'label':>15}")
def txt(k):
    t, a, b, c = k
    return f"{a}(x,y) => {c}(y,x)" if t == "I" else f"{a}(x,y) & {b}(y,z) => {c}(x,z)"
for k, c in sorted(cat.items(), key=lambda kv: (-kv[1]["runs"], txt(kv[0]))):
    tc = st.mean([x for x in c["true_conf"] if x is not None])
    label = c["designed"] or ("valid (found, not designed)" if tc >= 0.99 else ("weak/decoy" if tc < 0.9 else "near-law"))
    lines.append(f"{txt(k):78} {c['by_cov'][30]:>4}/{c['by_cov'][50]}/{c['by_cov'][70]:<5} {tc:>9.2f} {st.mean(c['agree']):>6.2f} {label:>15}")
text = "\n".join(lines)
open("results/aggregate.txt", "w").write(text + "\n")
print(text)
