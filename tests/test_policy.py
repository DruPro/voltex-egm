"""voltex3 custom inference policies: SDK and CLI (egm/policy.py, docs/POLICIES.md)."""
import json, os, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import egm  # noqa: E402
from egm.policy import PolicyError, PolicyRegistry  # noqa: E402
import worlds  # noqa: E402

EGM = [sys.executable, os.path.join(ROOT, "bin", "egm")]


class Policies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.facts = os.path.join(cls.tmp.name, "harvest.txt")
        with open(cls.facts, "w") as f:   # harvest: an over-general rule that only some policies admit
            f.write("\n".join(worlds.harvest()[0]) + "\n")

    def setUp(self):
        self.dir = tempfile.mkdtemp(dir=self.tmp.name)
        self.reg = PolicyRegistry(self.dir)

    def cli(self, *args):
        r = subprocess.run(EGM + list(args), capture_output=True, text=True,
                           env={**os.environ, "EGM_POLICY_DIR": self.dir})
        return r.returncode, r.stdout, r.stderr

    # 1. create, configure, retrieve, execute through the SDK
    def test_sdk_lifecycle(self):
        p = self.reg.create("loose", thresholds={"minSampleSize": 5}, validation={"method": "split_half", "required": False})
        self.assertEqual(p.id, "loose@1"); self.assertEqual(p.validation["method"], "internal_replication")
        p2 = self.reg.update("loose", thresholds={"minAgreement": 0.5})
        self.assertEqual(p2.id, "loose@2"); self.assertEqual(p2.thresholds["minSampleSize"], 5)
        self.assertEqual(self.reg.get("loose@1").thresholds["minAgreement"], 0.0)   # version 1 unchanged
        c = self.reg.clone("strict", "mine"); self.assertEqual(c.id, "mine@1")
        with egm.open(self.facts) as e:
            fs = e.infer_all(policy=p2)
            self.assertTrue(fs); self.assertTrue(all(f.policy == "loose@2" for f in fs))
            self.assertEqual(e.policy.id, "legacy@builtin-1")    # restored after the call

    # 2. the same through the CLI, and 3. SDK and CLI give the same results
    def test_cli_lifecycle_and_equivalence(self):
        self.assertEqual(self.cli("policy", "create", "c1", "--set", "thresholds.minSampleSize=5",
                                  "--set", "validation.required=false")[0], 0)
        code, out, err = self.cli("policy", "configure", "c1", "--set", "thresholds.minAgreement=0.5")
        self.assertEqual(code, 0, err); self.assertTrue(out.startswith("c1@2"))
        self.assertIn("c1", self.cli("policy", "list")[1])
        self.assertEqual(json.loads(self.cli("policy", "show", "c1@2")[1])["thresholds"]["minAgreement"], 0.5)
        code, out, err = self.cli("infer", self.facts, "--policy", "c1", "--json")
        self.assertEqual(code, 0, err); cli = json.loads(out)
        self.assertEqual(cli["policy"], "c1@2")
        with egm.open(self.facts) as e:
            sdk = e.infer_all(policy=self.reg.get("c1"))
            self.assertEqual(sorted(f["fact"] for f in cli["facts"]), sorted(f.fact for f in sdk))
            self.assertEqual(cli["snapshot"], e.snapshot())
        code, out, err = self.cli("policy", "compare", self.facts, "strict", "tendency", "c1", "--json")
        self.assertEqual(code, 0, err); self.assertEqual(len(json.loads(out)["summary"]), 3)
        exp = os.path.join(self.dir, "c1.json")
        self.assertEqual(self.cli("policy", "export", "c1", "-o", exp)[0], 0)
        self.assertEqual(self.cli("policy", "import", exp, "--name", "c2")[1].strip(), "c2@1")
        self.assertEqual(self.reg.get("c2").config(), self.reg.get("c1").config())

    # 4. a threshold change gives an observable, explainable change
    def test_threshold_change_is_observable_and_explained(self):
        loose = self.reg.create("loose", validation={"required": False})
        tight = self.reg.create("tight", thresholds={"minReliability": 0.95}, validation={"required": False})
        with egm.open(self.facts) as e:
            a = {f.fact for f in e.infer_all(policy=loose)}; b = {f.fact for f in e.infer_all(policy=tight)}
            self.assertTrue(b < a)                                   # the tighter policy derives strictly less
            e.apply_policy(tight)
            dropped = [v for v in e.evidence() if v["admit"] == "none"]
            self.assertTrue(dropped)                                 # the rules it no longer admits ...
            self.assertTrue(all(v["rel"] < 0.95 or v["one_value"] for v in dropped))   # ... fall below the threshold
            e.apply_policy("legacy")

    # 5. policies never alter the evidence
    def test_evidence_unchanged(self):
        with egm.open(self.facts) as e:
            s0 = e.snapshot(); stated0 = [f.fact for f in e.ask("? harvests ?") if f.status == "stated"]
            for p in ("strict", "tendency", self.reg.create("x", thresholds={"minAgreement": 0.99})):
                e.infer_all(policy=p); e.compare_policies(["strict", "tendency"])
            self.assertEqual(e.snapshot(), s0)
            self.assertEqual([f.fact for f in e.ask("? harvests ?") if f.status == "stated"], stated0)

    # 6. a version reproduces its results after later versions exist
    def test_versions_reproduce(self):
        self.reg.create("r", validation={"required": False})
        with egm.open(self.facts) as e:
            first = sorted(f.fact for f in e.infer_all(policy=self.reg.get("r@1")))
            self.reg.update("r", thresholds={"minReliability": 0.95})
            again = sorted(f.fact for f in e.infer_all(policy=self.reg.get("r@1")))
            self.assertEqual(first, again)

    # 7. invalid configurations fail explicitly, in the SDK, the CLI and the engine
    def test_invalid_configurations_fail(self):
        for bad in ({"thresholds": {"minAgrement": 0.5}}, {"thresholds": {"minAgreement": 1.5}},
                    {"thresholds": {"minSampleSize": 2.5}}, {"validation": {"method": "independent_sources"}},
                    {"validation": {"split": "random"}}, {"inference": {"shapes": ["spiral"]}},
                    {"inference": {"shapes": []}}, {"bogus": {}}):
            with self.assertRaises(PolicyError, msg=str(bad)):
                self.reg.create("bad", **{k: v for k, v in bad.items() if k in ("thresholds", "validation", "inference")}) \
                    if "bogus" not in bad else egm.policy.validate(bad)
        with self.assertRaises(PolicyError):
            self.reg.update("strict", thresholds={"minAgreement": 0.5})
        with self.assertRaises(PolicyError):
            self.reg.get("nosuch")
        code, out, err = self.cli("policy", "create", "b", "--set", "thresholds.minAgreement=7")
        self.assertNotEqual(code, 0); self.assertIn("minAgreement", err)
        with egm.Engine() as e:   # the engine validates too, and leaves the policy unchanged
            out = e.cmd("POLICY APPLY p 1 core.nonsense=1")
            self.assertTrue(any(l.startswith("[ERROR] unknown policy field") for l in out))
            self.assertEqual(e.cmd("POLICY SHOW"), ["[POLICY] legacy"])

    # 8. legacy behaviour is unchanged by the policy machinery
    def test_legacy_unchanged(self):
        with egm.open(self.facts) as e:
            before = sorted((f.fact, f.tier) for f in e.infer_all())
            e.infer_all(policy="strict"); e.infer_all(policy="tendency")
            after = sorted((f.fact, f.tier) for f in e.infer_all(policy="legacy"))
            self.assertEqual(before, after)
            self.assertTrue(all(t in ("law", "tendency") for _, t in before))

    def test_insufficient_is_not_failed(self):
        """A rule with too few known answers in a half is reported insufficient, and the policy decides what to do."""
        rej = self.reg.create("rej", validation={"required": True, "minPerHalf": 10**9, "onInsufficient": "reject"})
        adm = self.reg.create("adm", validation={"required": True, "minPerHalf": 10**9, "onInsufficient": "admit"})
        with egm.open(self.facts) as e:
            e.apply_policy(rej)
            self.assertTrue(all(v["validation"].endswith(":insufficient") for v in e.evidence()))
            self.assertEqual(e.infer_all(), [])
            self.assertTrue(e.infer_all(policy=adm))
            e.apply_policy("legacy")
        with self.assertRaises(PolicyError):
            self.reg.create("bad", validation={"onInsufficient": "maybe"})

    def test_weakest_evidence_reported_under_a_policy(self):
        with egm.open(self.facts) as e:
            fs = e.infer_all(policy=self.reg.create("w", validation={"required": False}))
            self.assertTrue(fs and all(f.weakest is not None and 0 <= f.weakest <= 1 for f in fs))
            self.assertTrue(all(f.weakest is None for f in e.infer_all()))     # legacy output is unchanged

    def test_nesting_of_builtins(self):
        with egm.open(self.facts) as e:
            c = e.compare_policies(["strict", "tendency"])
            self.assertTrue(c.contained["strict@builtin-1 in tendency@builtin-1"])


if __name__ == "__main__":
    unittest.main()
