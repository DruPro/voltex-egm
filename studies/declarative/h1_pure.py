"""H1: can unmodified v2.1 supersede a value through ingestion alone? (PREREGISTRATION.md)"""
import sys, re, json, subprocess, statistics as st
sys.path.insert(0, "/home/claude/work/amend"); sys.argv = sys.argv[:1]
exec(open("/home/claude/work/amend/exp_amend.py").read().split("if __name__")[0])
V21 = "/home/claude/work/v21/voltex2"
rows = []
for seed in [1, 2, 3, 4, 5]:
    w = world(seed, 0.5); moves, region, tl = make_moves(w, seed, 0.15)
    for probe in ["P0_plain", "P1_plain_x5", "P2_formerly"]:
        extra = []
        for p, (o, n) in sorted(moves.items()):
            reps = 5 if probe == "P1_plain_x5" else 1
            extra += [f"INGEST {p} lives in {n}"] * reps
            if probe == "P2_formerly": extra.append(f"INGEST {p} formerly lived in {o}")
        asks = [f"ASK {p} lives in ?" for p in sorted(moves)]
        out = subprocess.run([V21], input="\n".join([f"INGESTFILE {w['path']}"] + extra + ["RELATIONS", "CONFLICTS"] + asks + ["EXIT"]) + "\n",
                             capture_output=True, text=True).stdout
        open(f"/home/claude/work/declarative/logs/h1_{probe}_s{seed}.log", "w").write(out)
        # answers per mover: collect lines after each ASK block. ASK output is "  <fact>  stated|inferred ..."
        stated = {}
        for l in out.splitlines():
            m = re.match(r"\s+(\S+) lives in (\S+)\s+stated", l)
            if m and m.group(1) in moves: stated.setdefault(m.group(1), set()).add(m.group(2))
        old_still = sum(moves[p][0] in stated.get(p, set()) for p in moves)
        new_only = sum(stated.get(p, set()) == {moves[p][1]} for p in moves)
        flagged = sum(1 for l in out.splitlines() if l.startswith("CONFLICT\t") and l.split("\t")[1] in moves and " lives in " in l)
        rel_formerly = any("formerly lived in" in l for l in out.splitlines() if l.strip().startswith("#") or "ACCEPT" in l)
        acc_formerly = [l.strip()[:150] for l in out.splitlines() if "ACCEPT" in l and "formerly" in l]
        rows.append({"seed": seed, "probe": probe, "movers": len(moves), "old_still_current": old_still / len(moves),
                     "new_value_alone": new_only / len(moves), "lives_in_conflicts_on_movers": flagged,
                     "formerly_relation_formed": rel_formerly, "accepted_rules_with_formerly": acc_formerly})
        print(seed, probe, rows[-1]["old_still_current"], rows[-1]["new_value_alone"], flagged, rel_formerly, len(acc_formerly), flush=True)
json.dump(rows, open("/home/claude/work/declarative/results_h1.json", "w"), indent=1)
for probe in ["P0_plain", "P1_plain_x5", "P2_formerly"]:
    R = [r for r in rows if r["probe"] == probe]
    print(f"{probe:12} old value still stated as current: {st.mean(r['old_still_current'] for r in R):.3f}   new value alone: {st.mean(r['new_value_alone'] for r in R):.3f}   "
          f"conflicts on movers: {sum(r['lives_in_conflicts_on_movers'] for r in R)}   'formerly' relation formed: {sum(r['formerly_relation_formed'] for r in R)}/5")
