"""Validate the confirmation harness before confirmation, on planted cases and development worlds only (the sealed
worlds are not touched). Writes confirm/harness_validation.json and prints a summary.

  1. Counterfactual checker on planted engines: faithful (-> removed), second proof (-> alternative),
     fabricated proof (-> FAIL), missing proof (-> FAIL).
  2. Counterfactual checker on the real engine, development worlds, policies strict and tendency: expected 0 FAIL.
  3. Proof-validity checker (metrics.proof_validity) on a planted invalid run: must report it.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "capability", "tools")); sys.path.insert(0, ROOT)
from interface import Answer, EGMAdapter, Run, parse_fact  # noqa: E402
import counterfactual, cworlds, metrics  # noqa: E402

RELS = ["contains", "is in", "is near"]


class Planted:
    """A tiny rule engine: X is in Y because Y contains X; with `alt`, also because X is near Y (a second proof)."""
    def __init__(self, mode):
        self.mode = mode

    def _derive(self, lines):
        S = {f for f in (parse_fact(l, RELS) for l in lines) if f}
        out = {}
        for r, a, b in S:
            if r == "contains" and ("is in", b, a) not in S:
                out[("is in", b, a)] = [("contains", a, b)]
            if self.mode == "alt" and r == "is near" and ("is in", a, b) not in S and ("is in", a, b) not in out:
                out[("is in", a, b)] = [("is near", a, b)]
        if self.mode == "fabricate":
            out[("is in", "i0", "b0")] = [("contains", "b0", "i0")]          # claims a premise whatever the evidence
        if self.mode == "noproof":
            out = {f: [] for f in out}
        return out

    def run(self, lines, rels, probes):
        return Run([Answer(f, "derived", 1.0, p, "planted") for f, p in self._derive(lines).items()], {}, set(), 0, None, {"planted"})

    def ask(self, lines, rels, subject, relation):
        return [Answer(f, "derived", 1.0, p, "planted") for f, p in self._derive(lines).items() if f[1] == subject and f[0] == relation]


def planted_lines(alt=False):
    L = [f"b{i} contains i{i}" for i in range(5)]
    if alt:
        L += [f"i{i} is near b{i}" for i in range(5)]
    return L


def main():
    res = {"planted": {}, "development": {}, "proof_validity": {}}
    for mode, alt, expect in (("faithful", False, "removed"), ("alt", True, "alternative"),
                              ("fabricate", False, "FAIL"), ("noproof", False, "FAIL")):
        eng = Planted(mode); lines = planted_lines(alt)
        out = counterfactual.check(eng, lines, RELS, eng.run(lines, RELS, []), n=5, seed=0)
        got = {r["outcome"] for r in out}
        res["planted"][mode] = {"expected": expect, "outcomes": sorted(got), "ok": expect in got and (expect != "FAIL" or True)}
        if mode in ("faithful", "alt"):
            res["planted"][mode]["ok"] = got == {expect}
        print(f"planted {mode:10s} expected {expect:12s} got {sorted(got)}")
    for world in ("company", "hidden-cov50", "remainders", "harvest"):
        w = cworlds.load(world, 0)
        for pol in ("strict", "tendency"):
            a = EGMAdapter(policy=pol)
            out = counterfactual.check(a, w.lines, w.rels, a.run(w.lines, w.rels, []), n=20, seed=0)
            s = counterfactual.summarize(out)
            res["development"][f"{world}/{pol}"] = {"summary": s, "fails": [r for r in out if r["outcome"] == "FAIL"]}
            print(f"development {world:13s} {pol:9s} {s}")
    # proof validity: a planted run whose answer cites a premise that is neither stated nor derived
    w = cworlds.load("company", 0)
    bad = Run([Answer(("lives in", "zz_nobody", "zz_town"), "derived", 1.0, [("works at", "zz_nobody", "zz_nowhere")], "r")],
              {}, set(), 0, None, {"r"})
    m = metrics.measure(w, bad)
    res["proof_validity"] = {"proofs_checked": m["proofs_checked"], "proofs_invalid": m["proofs_invalid"]}
    print("planted invalid proof:", res["proof_validity"])
    ok = all(v["ok"] for v in res["planted"].values()) and m["proofs_invalid"] == 1 and \
        all(v["summary"]["FAIL"] == 0 for v in res["development"].values())
    res["harness_valid"] = ok
    json.dump(res, open(os.path.join(HERE, "harness_validation.json"), "w"), indent=1, default=list)
    print("HARNESS VALID" if ok else "HARNESS NOT VALID")


if __name__ == "__main__":
    main()
