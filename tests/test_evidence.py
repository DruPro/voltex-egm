"""voltex3 contract tests for the evidence vector (studies/evidence_policy/DESIGN.md, sections 3.1 and 6)."""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import egm  # noqa: E402
import worlds  # noqa: E402


class EvidenceVector(unittest.TestCase):
    def vectors(self, lines, settings=None):
        with egm.Engine(settings=settings or {}) as e:
            e.ingest_many(lines)
            return e.evidence(include_rejected=True), e.rules(include_rejected=True)

    def test_components_partition_chains(self):
        """E+ + E- + E? = n for one-value conclusions; E- = 0 otherwise (a missing conclusion is unknown there)."""
        for lines in (worlds.staff()[0], worlds.remainders()[0], worlds.harvest()[0]):
            ev, _ = self.vectors(lines)
            self.assertTrue(ev)
            for v in ev:
                self.assertLessEqual(v["e_plus"] + v["e_minus"] + v["e_unknown"], v["n"], v["rule"])
                if v["one_value"]:
                    self.assertEqual(v["e_plus"] + v["e_minus"] + v["e_unknown"], v["n"], v["rule"])
                else:
                    self.assertEqual(v["e_minus"], 0, v["rule"])

    def test_vector_matches_rule_scores(self):
        """The vector is computed from the same counts as the rule list: same rules, same n, k and acceptance."""
        ev, rules = self.vectors(worlds.staff()[0])
        rs = {r.text: r for r in rules}
        for v in ev:
            if v["rule"] in rs:
                self.assertEqual(rs[v["rule"]].n, v["n"]); self.assertEqual(rs[v["rule"]].k, v["e_plus"])
                self.assertEqual(rs[v["rule"]].accepted, v["accepted"])

    def test_tree_rules_have_vectors(self):
        ev, _ = self.vectors(worlds.gates()[0], {"TREES": 1})
        self.assertTrue(any(v["rule"].startswith("TREE") and v["accepted"] for v in ev))


if __name__ == "__main__":
    unittest.main()
