"""Equivalence gate: binary B must give byte-identical output to the frozen engine A on every dataset x settings cell.

Usage: python3 gate.py A B [extra settings for B only, e.g. CLUSTERSTREAM=1]
Lines that legitimately vary are dropped before comparing: ingest throughput ("MB/s"), [PROFILE] and [LAB] timings, and
the METRICS "Process RSS" line. Prints one line per differing cell and a summary; exit status 1 if any cell differs.
"""
import hashlib, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tests")); sys.path.insert(0, os.path.join(ROOT, "studies", "noise", "tools"))
import worlds   # noqa: E402
import lib      # noqa: E402
STUDY = os.path.abspath(os.path.join(HERE, ".."))
GD = os.path.join(STUDY, "obs", "gate")

SETTINGS = {"default": {}, "trees": {"TREES": 1}, "chain3": {"CHAIN": 3}, "conditions": {"CONDITIONS": 1},
            "vote": {"VOTE": 1}, "quarantine": {"QUARANTINE": 1}, "replicate": {"REPLICATE": 1},
            "v20": {"COVERAGE": 0, "LABELS": 0, "CORROBORATE": 0, "STALE": 0}, "class03": {"CLASS": 0.3},
            "class07": {"CLASS": 0.7}, "maxwords300": {"MAXWORDS": 300}, "depth0": {"DEPTH": 0}, "tsteps0": {"TENDENCYSTEPS": 0}}


def datasets():
    os.makedirs(GD, exist_ok=True)
    d = {}
    for f in ("tokenomics/S.txt", "tokenomics/M.txt", "tokenomics/L.txt", "requests/facts_haiku.txt"):
        d["ex_" + f.replace("/", "_")] = os.path.join(ROOT, "examples", f)
    gen = {"t_lineage": worlds.lineage()[0], "t_gates": worlds.gates()[0], "t_remainders": worlds.remainders()[0],
           "t_harvest": worlds.harvest()[0], "t_staff": worlds.staff()[0], "t_staff_noisy": worlds.staff(noise=0.15, reports=3)[0],
           "n_company1": lib.gen.company(seed=0, scale=1)[0], "n_company4_n15": lib.gen.company(seed=0, scale=4, noise=0.15)[0],
           "n_company1_r3": lib.gen.company(seed=0, scale=1, noise=0.15, reports=3)[0],
           "n_hidden1": lib.gen.hidden(seed=0, scale=1)[0], "n_hidden2_n15": lib.gen.hidden(seed=1, scale=2, noise=0.15)[0],
           "n_gates200_n05": lib.gen.gates(seed=0, per_kind=200, noise=0.05)[0], "n_lineage": lib.gen.lineage(seed=0)[0]}
    for k, lines in gen.items():
        p = os.path.join(GD, k + ".txt"); open(p, "w").write("\n".join(lines) + "\n"); d[k] = p
    return d


def body(path, st, kb):
    return "\n".join([f"SET {k} {v}" for k, v in st.items()] + [
        f"INGESTFILE {path}", "RELATIONS", "INFER ALL", "INFER", "CONFLICTS", "CLASSES", "CHAINS", "METRICS",
        "ASK ? is on ?", "ASK ? has value ?", f"SAVE {kb}", f"LOAD {kb}", "INFER ALL", "EXIT"]) + "\n"


def clean(out):
    return "\n".join(l for l in out.splitlines() if "MB/s" not in l and not l.startswith("[PROFILE]") and
                     not l.startswith("[LAB]") and "Process RSS" not in l)


def main():
    A, B = sys.argv[1], sys.argv[2]
    extraB = dict(x.split("=", 1) for x in sys.argv[3:])
    ds = datasets(); same = cells = 0; rows = []
    with tempfile.TemporaryDirectory(prefix="gate_") as td:
        for name, path in sorted(ds.items()):
            for sname, st in SETTINGS.items():
                kb = os.path.join(td, "kb.vtx")
                a = clean(subprocess.run([A], input=body(path, st, kb), capture_output=True, text=True).stdout)
                b = clean(subprocess.run([B], input=body(path, {**extraB, **st}, kb), capture_output=True, text=True).stdout)
                b = "\n".join(l for l in b.splitlines() if not any(l.startswith(f"[SET] {k} = ") for k in extraB))   # B's extra SET echo
                # B's extra settings named in [CONFIG] notices (experimental settings on, restored from .cfg): drop only that token,
                # and drop a notice that names nothing else
                bl = []
                for l in b.splitlines():
                    if l.startswith("[CONFIG]"):
                        for k, v in extraB.items(): l = l.replace(f" {k}={v}", "")
                        if l.endswith(":"): continue
                    bl.append(l)
                b = "\n".join(bl)
                cells += 1; ok = a == b; same += ok
                rows.append({"dataset": name, "settings": sname, "identical": ok, "sha_a": hashlib.sha256(a.encode()).hexdigest()[:16],
                             "sha_b": hashlib.sha256(b.encode()).hexdigest()[:16], "lines": a.count("\n") + 1})
                if not ok: print("differs:", name, sname, flush=True)
    print(f"gate: {same}/{cells} identical")
    tag = os.environ.get("GATE_TAG")
    if tag:
        json.dump({"A": A, "B": os.path.basename(B), "extraB": extraB, "identical": same, "cells": cells, "rows": rows},
                  open(os.path.join(STUDY, f"results_gate_{tag}.json"), "w"), indent=1)
    sys.exit(0 if same == cells else 1)


if __name__ == "__main__":
    main()
