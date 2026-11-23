"""Validate the Round 2 harness without running EGM on any confirmation data.

  1. Metrics on the Round 2 generator's format, with planted engines on sealed2 seed 0 (a self-check seed of the
     generator's author, not a confirmation seed): an oracle that asserts exactly the hidden facts (precision 1,
     recall 1, abstention 1); an engine that asserts every undeterminable fact it can name (abstention 0 on
     [rel, subj, obj] keys, as on [rel, subj] keys).
  2. realdata2 loads: truth is the partition of stated + key; recall truth is the key; no EGM.
  3. confirm2.py dry: the full pipeline on development data.
Writes harness_validation.json.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import confirm2  # noqa: E402
from interface import Answer, Run  # noqa: E402
import metrics, cworlds  # noqa: E402


class Planted:
    def __init__(self, facts):
        self.facts = facts

    def run(self, lines, rels, probes):
        return Run([Answer(f, "derived", 1.0, [], "planted") for f in self.facts], {}, set(), 0, None, {"planted"})


def main():
    import gen_sealed2
    res = {"format": {}, "realdata": {}}
    ok = True
    for st in confirm2.STRUCTURES:
        w = confirm2.sealed_world(st, 0); lines, key = gen_sealed2.world(st, 0)
        S = cworlds.stated(w)
        o = metrics.measure(w, Planted(sorted(w.recall_truth)).run(w.lines, w.rels, []))
        und = [tuple(x) for x in key["undeterminable"]]
        # assert something for each undeterminable key: the true fact for 3-element keys, a made-up object for 2
        guess = set()
        for k in und:
            if len(k) == 3:
                guess.add(k)
            else:
                guess.add((k[0], k[1], "zz_guess"))
        g = metrics.measure(w, Planted(sorted(guess)).run(w.lines, w.rels, [])) if und else None
        r = {"oracle_precision": o["precision"], "oracle_recall": o["recall"], "oracle_abstention": o["abstention"],
             "guess_abstention": g["abstention"] if g else None, "undet_keys": len(und),
             "three_element_keys": sum(1 for k in und if len(k) == 3), "hidden": len(w.recall_truth)}
        good = (not w.recall_truth or (o["precision"] == 1.0 and o["recall"] == 1.0)) and \
               (not und or (o["abstention"] == 1.0 and g["abstention"] == 0.0))
        r["ok"] = good; ok &= good; res["format"][st] = r
        print(st, r)
    import realdata2
    for name in realdata2.SETS:
        w = realdata2.load(name, 2000)
        good = w.recall_truth <= w.truth and not (w.recall_truth & cworlds.stated(w)) and len(w.truth) == len(cworlds.stated(w)) + len(w.recall_truth)
        res["realdata"][name] = {"truth": len(w.truth), "hidden": len(w.recall_truth), "ok": good}; ok &= good
        print(name, res["realdata"][name])
    confirm2.dry()
    res["dry_run"] = "see dry_run.json"
    res["harness_valid"] = ok
    json.dump(res, open(os.path.join(HERE, "harness_validation.json"), "w"), indent=1)
    print("HARNESS VALID" if ok else "HARNESS NOT VALID")


if __name__ == "__main__":
    main()
