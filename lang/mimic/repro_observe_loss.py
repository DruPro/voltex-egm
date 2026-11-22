"""Reproduction (for the engine owner): a record's current snapshot facts disappear after a fixed number of snapshots.

  python3 lang/mimic/repro_observe_loss.py

What it does, on a plain engine (no Mimic runtime in the loop):
  1. Load the taught examples of examples/increment.mim (teach K), with the settings TREES 1, DEPTH 0, TENDENCYSTEPS 0.
  2. Ingest three plain facts that name entity S: "W is write of S", "M is move of S", "N is next of S".
  3. OBSERVE record S as a snapshot at t = 1, 2, 3, ... with "S inc_reads v1|v0" in the pattern 1, 1, 0 (and, in
     the second variant, also "S inc_state vcarry").
  4. After each snapshot, ask "S inc_reads ?".

Observed: the current fact is gone (no stated or current answer, and the relation loses one fact) at snapshot 13 with
one fact per snapshot, and 26 with two. The same at teach 16, 32, 64 and 128. Not seen without the plain facts about
S, without the taught knowledge base (a tiny `lives in` world with the same plain fact survived 79 snapshots), or in
the same steps run with fresh entities or a rebuilt engine.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import egm     # noqa: E402
import mimic   # noqa: E402

ST = {"TREES": 1, "DEPTH": 0, "TENDENCYSTEPS": 0, "MAXWORDS": 12000}


def lost_at(per, K=64, limit=200):
    base = open(os.path.join(HERE, "examples", "increment.mim")).read().split("run inc")[0]
    p = mimic.Program.parse(f"teach {K}\n" + base); R = mimic.Runtime(p, mode="fresh", out=lambda s: None)
    taught = R.taught; R.e.close(); path = os.path.join(R.tmp.name, "t.txt"); open(path, "w").write("\n".join(taught) + "\n")
    with egm.open(path, settings=ST, binary=os.path.join(ROOT, "build", "voltex2")) as e:
        e.ingest_many(["W is write of S", "M is move of S", "N is next of S"])
        for t in range(1, limit):
            facts = [f"S inc_reads v{1 if t % 3 else 0}"] + (["S inc_state vcarry"] if per == 2 else [])
            e.observe("mimic", "S", t, facts=facts)
            if not [f for f in e.ask("S inc_reads ?") if f.status in ("stated", "current")]: return t
    return None


if __name__ == "__main__":
    for per in (1, 2):
        print(f"{per} fact(s) per snapshot: current fact lost at snapshot {lost_at(per)}")
