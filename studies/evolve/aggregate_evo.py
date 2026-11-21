import json, sys, collections, statistics as st
R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "results_main.json"))
runs = R["runs"]; conds = ["A", "B", "D", "V22", "V22off", "V22x"]
present = [c for c in conds if any(r["cond"] == c for r in runs)]
def cell(rows):
    c = collections.Counter(p["grade"] for p in rows); n = sum(c.values())
    if not n: return "   -  "
    s = f"{c['right'] / n:.2f}"
    extra = [f"w{c['wrong'] / n:.2f}" if c["wrong"] else "", f"a{c['abstain'] / n:.2f}" if c["abstain"] else "", f"m{c['ambiguous'] / n:.2f}" if c["ambiguous"] else ""]
    return s + ("(" + ",".join(e for e in extra if e) + ")" if any(extra) else "")
def probes(world=None, sc=None, kind=None, tag=None, cond=None):
    out = []
    for r in runs:
        if (world and r["world"] != world) or (cond and r["cond"] != cond): continue
        for p in r["probes"]:
            if (sc and p["sc"] != sc) or (kind and p["kind"] != kind) or (tag is not None and p["tag"] != tag): continue
            out.append(p)
    return out
table = collections.OrderedDict()
order = [("people", ["ch", "stale", "samereg", "multi", "corr", "src", "compat", "miss", "part1", "part2", "ooo", "vol"]),
         ("database", ["db_move", "db_mgr", "db_proj", "db_corr", "db_src", "db_ooo"]),
         ("code", ["code_keep", "code_drop", "code_move", "code_add", "code_ooo"])]
print("share right (w=wrong a=abstain m=ambiguous), pooled over seeds; one row per scenario x probe kind x tag")
print(f"{'world':8} {'scenario':10} {'probe':22} {'n':>4} " + " ".join(f"{c:>18}" for c in present))
for wn, scs in order:
    for sc in scs:
        keys = list(dict.fromkeys((p["kind"], p["tag"]) for p in probes(wn, sc, cond=present[0])))
        for k, tg in keys:
            n = len(probes(wn, sc, k, tg, present[0]))
            print(f"{wn:8} {sc:10} {(k + ':' + tg if tg else k):22} {n:4} " + " ".join(f"{cell(probes(wn, sc, k, tg, c)):>18}" for c in present))
print("\npersistence (sessions with identical answers after SAVE/LOAD):", {c: f"{sum(1 for r in runs if r['cond'] == c and r['persist'])}/{sum(1 for r in runs if r['cond'] == c)}" for c in present})
print("\nrule discovery: mean accepted true rules per session vs the no-update base run (same world and seed)")
base = {(b["world"], b["seed"]): b for b in R["base_only"]}
for wn, _ in order:
    line = f"{wn:8}"
    for c in present:
        rs = [r for r in runs if r["world"] == wn and r["cond"] == c]
        if not rs: continue
        d = [r["true_rules"] - base[(wn, r["seed"])][c]["true_rules"] for r in rs]
        dd = [r["decoys"] - base[(wn, r["seed"])][c]["decoys"] for r in rs]
        b0 = st.mean(base[(wn, r["seed"])][c]["true_rules"] for r in rs)
        line += f"  {c}: base {b0:.1f}, after {st.mean(r['true_rules'] for r in rs):.1f} (max |d| {max(map(abs, d))}, decoys d {max(map(abs, dd), default=0)})"
    print(line)
print("\ncost: mean session seconds, update commands/bytes, saved bytes (per world)")
for wn, _ in order:
    print(wn, {c: (round(st.mean(r["seconds"] for r in runs if r["world"] == wn and r["cond"] == c), 2),
                   round(st.mean(r["update_bytes"] for r in runs if r["world"] == wn and r["cond"] == c)),
                   round(st.mean(r["save_bytes"] for r in runs if r["world"] == wn and r["cond"] == c))) for c in present})
