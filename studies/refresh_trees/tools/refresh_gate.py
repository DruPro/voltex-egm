"""R2: the regression gate's datasets x settings, through a script that exercises the REFRESH path.

  python3 refresh_gate.py BASELINE NEW      writes ../results_refresh_gate.json

Each cell: SET REFRESH 0.05 plus the cell's settings; ingest the dataset; RELATIONS; INFER ALL; then retract and
re-ingest 5 stated facts (the same words, so the refresh path's no-new-words condition holds); INFER ALL; CONFLICTS;
CHAINS. Output is normalised as the gate does. Raw [PROFILE] lines are kept separately to record which build path
each binary took ("refresh:" = classes and rules reused).
"""
import hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "scaling", "tools"))
import gate  # noqa: E402  (datasets, SETTINGS, clean)


def body(path, st):
    lines = [l.strip() for l in open(path) if l.strip()]
    step = max(1, len(lines) // 5); pick = lines[::step][:5]
    cmds = ["SET PROFILE 1", "SET REFRESH 0.05"] + [f"SET {k} {v}" for k, v in st.items()] + \
           [f"INGESTFILE {path}", "RELATIONS", "INFER ALL"] + [f"RETRACT {l}" for l in pick] + [f"INGEST {l}" for l in pick] + \
           ["INFER ALL", "CONFLICTS", "CHAINS", "EXIT"]
    return "\n".join(cmds) + "\n"


def main():
    A, B = sys.argv[1], sys.argv[2]
    rows = []; same = 0
    for name, path in sorted(gate.datasets().items()):
        for sname, st in gate.SETTINGS.items():
            ra = subprocess.run([A], input=body(path, st), capture_output=True, text=True).stdout
            rb = subprocess.run([B], input=body(path, st), capture_output=True, text=True).stdout
            a, b = gate.clean(ra), gate.clean(rb); ok = a == b; same += ok
            rows.append({"dataset": name, "settings": sname, "trees": "TREES" in st, "identical": ok,
                         "sha_a": hashlib.sha256(a.encode()).hexdigest()[:16], "sha_b": hashlib.sha256(b.encode()).hexdigest()[:16],
                         "refresh_a": ra.count("refresh:"), "refresh_b": rb.count("refresh:")})
            if not ok: print("differs:", name, sname, "(trees)" if "TREES" in st else "", flush=True)
    non_trees = [r for r in rows if not r["trees"]]
    summary = {"cells": len(rows), "identical": same, "non_tree_cells": len(non_trees),
               "non_tree_identical": sum(r["identical"] for r in non_trees),
               "tree_cells": len(rows) - len(non_trees), "tree_identical": sum(r["identical"] for r in rows if r["trees"]),
               "tree_cells_refresh_taken_new": sum(1 for r in rows if r["trees"] and r["refresh_b"] > 0),
               "tree_cells_refresh_taken_baseline": sum(1 for r in rows if r["trees"] and r["refresh_a"] > 0)}
    json.dump({"summary": summary, "rows": rows}, open(os.path.join(HERE, "..", "results_refresh_gate.json"), "w"), indent=1)
    print(summary)


if __name__ == "__main__":
    main()
