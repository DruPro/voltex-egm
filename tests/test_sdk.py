"""SDK tests (stdlib unittest; pytest also collects them).   python3 -m unittest tests/test_sdk.py -v"""
import json
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.environ.get("EGM_TEST_INSTALLED") != "1":     # test the checkout unless told to test an installed package
    sys.path.insert(0, ROOT)
import egm  # noqa: E402
from egm import bench, parse  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import worlds  # noqa: E402

EX = os.path.join(ROOT, "examples")
M = os.path.join(EX, "tokenomics", "M.txt")


def world(e):
    """People, cities, countries from three sources, with one change, one disagreement and a stale fact."""
    r = random.Random(1)
    cities = {"paris": "france", "rome": "italy", "oslo": "norway", "lima": "peru", "kyiv": "ukraine", "bonn": "germany"}
    ppl = [f"p{i}" for i in range(30)]
    home = {p: r.choice(list(cities)) for p in ppl}
    e.set("DX", 1)
    e.observe("atlas", "a1", 1, 1, "snapshot", [f"{c} is in {k}" for c, k in cities.items()])
    e.observe("census", "r1", 1, 1, "snapshot", [f"{p} lives in {home[p]}" for p in ppl])
    e.observe("atlas", "a2", 1, 1, "snapshot", [f"{p} is in {cities[home[p]]}" for p in ppl[:20]])
    home2 = dict(home); home2["p0"] = "oslo" if home["p0"] != "oslo" else "rome"
    e.observe("census", "r1", 2, 2, "snapshot", [f"{p} lives in {home2[p]}" for p in ppl])
    e.observe("gossip", "g1", 3, 1, "partial", [f"p1 lives in {'bonn' if home['p1'] != 'bonn' else 'lima'}"])
    return home, home2


class TestEngineBasics(unittest.TestCase):
    def test_version_and_binary(self):
        with egm.Engine() as e:
            self.assertTrue(os.path.isfile(e.binary))
            self.assertIn("2.2", e.version())
        self.assertEqual(egm.__version__, "2.2.1")

    def test_ingest_ids_are_stable(self):
        with egm.Engine() as e:
            a = e.ingest("x calls y"); b = e.ingest("x calls z"); c = e.ingest("x calls y")
            self.assertEqual(a, c); self.assertNotEqual(a, b)
            self.assertEqual(e.find("x calls y"), a)
            self.assertIn("x calls z", e); self.assertNotIn("x calls w", e)
            self.assertEqual(e.unroll(b), "x calls z")
            self.assertTrue(e.retract("x calls z")); self.assertFalse(e.retract("x calls z"))

    def test_ingest_many(self):
        with egm.Engine() as e:
            n = e.ingest_many([f"f{i} calls g{i % 4}" for i in range(20)] + ["", "  "])
            self.assertEqual(n, 20)
            self.assertEqual(e.values("? calls g1"), sorted(f"f{i}" for i in range(20) if i % 4 == 1))

    def test_closed_engine_raises(self):
        e = egm.Engine(); e.close()
        self.assertTrue(e.closed)
        with self.assertRaises(egm.EngineError):
            e.ask("a calls ?")

    def test_one_command_per_call(self):
        with egm.Engine() as e, self.assertRaises(ValueError):
            e.cmd("ASK a calls ?\nRELATIONS")

    def test_raw_cmd(self):
        with egm.Engine() as e:
            self.assertTrue(any("INGEST" in l for l in e.cmd("HELP")))


class TestKnowledgeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = egm.open(M)

    @classmethod
    def tearDownClass(cls):
        cls.e.close()

    def test_ask_stated(self):
        f = self.e.ask("? calls requests__select_proxy")
        self.assertEqual({x.subject for x in f}, {"requests__HTTPAdapter_get_connection",
                                                  "requests__HTTPAdapter_get_connection_with_tls_context",
                                                  "requests__HTTPAdapter_request_url"})
        self.assertTrue(all(x.status == "stated" and x.relation == "calls" for x in f))

    def test_inferred_has_proof(self):
        inf = [x for x in self.e.ask("requests__sessions imports ?") if x.status == "inferred"]
        self.assertTrue(inf)
        x = inf[0]
        self.assertEqual(x.tier, "tendency"); self.assertIsNotNone(x.score)
        self.assertEqual(len(x.because), 2); self.assertTrue(x.rule.startswith("[? imports ?]"))
        self.assertTrue(x.because[0].startswith("requests__sessions imports "))

    def test_strict_drops_tendency(self):
        all_ = self.e.ask("requests__sessions imports ?")
        strict = self.e.ask("requests__sessions imports ?", strict=True)
        self.assertLess(len(strict), len(all_))
        self.assertTrue(all(x.status == "stated" for x in strict))

    def test_values(self):
        v = self.e.values("requests__Session_send calls ?")
        self.assertIn("requests__dispatch_hook", v); self.assertEqual(v, sorted(v))
        self.assertEqual(self.e.values("requests__InvalidURL is defined in ?"), ["requests__exceptions"])

    def test_relations_and_rules(self):
        rel = {r.relation: r.facts for r in self.e.relations()}
        self.assertEqual(set(rel), {"is defined in", "calls", "imports", "raises", "inherits from"})
        self.assertEqual(rel["calls"], 602)
        acc = self.e.rules(); allr = self.e.rules(include_rejected=True)
        self.assertEqual(len(acc), 3); self.assertGreater(len(allr), len(acc))
        self.assertTrue(all(r.accepted for r in acc))
        r = acc[0]; self.assertGreater(r.n, 0); self.assertGreater(r.lift, 1); self.assertIn(r.tier, ("law", "tendency"))

    def test_infer_all(self):
        inf = self.e.infer_all()
        self.assertEqual(len(inf), 930)
        self.assertTrue(all(x.status == "inferred" and x.tier in ("law", "tendency") for x in inf))

    def test_unknown_relation(self):
        self.assertEqual(self.e.ask("requests__Session frobnicates ?"), [])
        with self.assertRaises(egm.RelationNotLearned) as cm:
            self.e.ask("requests__Session frobnicates ?", require=True)
        self.assertEqual(cm.exception.relation, "frobnicates")
        self.assertIn("calls", cm.exception.learned)
        self.assertIn("not a learned relation", self.e.explain("requests__Session frobnicates ?"))
        self.assertIsNone(self.e.explain("? calls requests__select_proxy"))

    def test_language_model_face(self):
        p = self.e.predict("requests__Session_send")
        self.assertTrue(p and p[0].token == "calls" and p[0].observed and 0 < p[0].p <= 1)
        q = self.e.query("requests__Session_send calls ?")
        self.assertTrue(any(x.token == "requests__dispatch_hook" for x in q))
        self.assertTrue(any(not x.observed for x in q))            # some fillers come from categories
        self.assertIsInstance(self.e.generate(), str)
        self.assertEqual(self.e.generate("requests__Session_send"), self.e.generate("requests__Session_send"))
        s = self.e.sample(3); self.assertEqual(len(s), 3)

    def test_categories_and_metrics(self):
        cats = self.e.categories()
        self.assertTrue(any(set(c.members) == {"calls", "raises", "imports"} for c in cats))
        m = self.e.metrics()
        self.assertTrue(m["records"].startswith("2490"))

    def test_to_dict_is_json(self):
        json.dumps([x.to_dict() for x in self.e.ask("requests__sessions imports ?")])


class TestChangingWorld(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = egm.Engine(); cls.home, cls.home2 = world(cls.e)

    @classmethod
    def tearDownClass(cls):
        cls.e.close()

    def test_snapshot_change_becomes_history(self):
        f = self.e.ask("p0 lives in ?")
        now = [x for x in f if x.is_current]; past = self.e.history("p0 lives in ?")
        self.assertEqual([x.object for x in now], [self.home2["p0"]])
        self.assertEqual(now[0].source, "census")
        self.assertEqual([x.object for x in past], [self.home["p0"]])
        self.assertEqual(past[0].status, "historical"); self.assertIn("until t=2", past[0].note)

    def test_sources_disagree(self):
        f = self.e.ask("p1 lives in ?")
        self.assertEqual(len(f), 2)
        self.assertTrue(all(x.flag == "sources_disagree" for x in f))
        self.assertIn("gossip says", f[0].note)

    def test_stale_and_current(self):
        f = self.e.ask("p0 is in ?")
        stale = [x for x in f if x.flag == "stale"]; cur = [x for x in f if x.status == "current"]
        self.assertEqual(len(stale), 1); self.assertFalse(stale[0].is_current); self.assertFalse(stale[0].is_strict)
        self.assertEqual(len(cur), 1); self.assertTrue(cur[0].is_current)
        self.assertEqual(cur[0].because, [f"p0 lives in {self.home2['p0']}", f"{self.home2['p0']} is in "
                                          + {"oslo": "norway", "rome": "italy"}[self.home2["p0"]]])
        self.assertIn("STALE", cur[0].note)
        self.assertEqual(self.e.values("p0 is in ?"), [cur[0].object])

    def test_inferred_for_unlisted_person(self):
        f = self.e.ask("p25 is in ?")
        self.assertEqual([(x.status, x.tier) for x in f], [("inferred", "tendency")])
        self.assertEqual(f[0].note, "1 of 1 paths agree")
        self.assertEqual(self.e.ask("p25 is in ?", strict=True), [])

    def test_conflicts(self):
        c = {x.subject: x for x in self.e.conflicts()}
        self.assertIn("p0", c); self.assertIn("p1", c)
        self.assertEqual(c["p1"].stated, "-"); self.assertIn("SOURCES DISAGREE", c["p1"].detail)

    def test_observe_validation(self):
        with self.assertRaises(ValueError):
            self.e.observe("a b", "r", 1, 1, "snapshot", ["x calls y"])
        with self.assertRaises(ValueError):
            self.e.observe("a", "r", 1, 1, "everything", ["x calls y"])
        with self.assertRaises(ValueError):
            self.e.observe("a", "r", 1, 1, "partial", ["x calls y ; z calls w"])


class TestPersistence(unittest.TestCase):
    def test_save_load_round_trip_with_observations(self):
        with tempfile.TemporaryDirectory() as td:
            kb = os.path.join(td, "w.vtx")
            with egm.Engine() as e:
                world(e); before = [x.to_dict() for x in e.ask("p0 lives in ?")]; e.save(kb)
            self.assertTrue(os.path.exists(kb + ".obs"))
            with egm.open(kb, settings={"DX": 1}) as e:
                self.assertEqual([x.to_dict() for x in e.ask("p0 lives in ?")], before)

    def test_settings_travel_with_the_knowledge_base(self):
        """C2/C4 (studies/config): a saved knowledge base keeps its settings; explicit settings override them."""
        with tempfile.TemporaryDirectory() as td:
            kb = os.path.join(td, "m.vtx")
            with egm.Engine(facts=[M]) as e:
                default_n = len(e.infer_all())
            with egm.Engine(facts=[M], settings={"RATE": 0.1, "PCA": 0.5}) as e:
                loose_n = len(e.infer_all()); e.save(kb)
            self.assertNotEqual(loose_n, default_n)
            self.assertTrue(os.path.exists(kb + ".cfg"))
            with egm.open(kb) as e:                                   # profile restored
                self.assertEqual(len(e.infer_all()), loose_n)
                self.assertEqual(e.config()["RATE"]["value"], 0.1)
            with egm.open(kb, settings={"RATE": 0.4, "PCA": 0.8}) as e:   # explicit settings win
                self.assertEqual(len(e.infer_all()), default_n)

    def test_knowledge_base_without_profile_keeps_old_behaviour(self):
        """C3: a .vtx without .cfg (saved by 2.2.1) loads with the current settings, as before."""
        with tempfile.TemporaryDirectory() as td:
            kb = os.path.join(td, "m.vtx")
            with egm.Engine(facts=[M]) as e:
                n = len(e.infer_all()); e.save(kb)
            os.remove(kb + ".cfg")
            with egm.open(kb) as e:
                self.assertEqual(len(e.infer_all()), n)

    def test_config_lists_every_setting(self):
        with egm.Engine() as e:
            c = e.config()
        self.assertGreaterEqual(len(c), 23)
        self.assertTrue(c["CHAIN"]["experimental"] and c["CONDITIONS"]["experimental"] and c["TREES"]["experimental"])
        self.assertFalse(c["DEPTH"]["experimental"])
        self.assertEqual((c["DEPTH"]["value"], c["CHAIN"]["value"]), (4, 2))

    def test_load_errors(self):
        with self.assertRaises(FileNotFoundError):
            egm.open("/nonexistent/kb.vtx")
        with tempfile.NamedTemporaryFile(suffix=".vtx") as bad:
            bad.write(b"not a knowledge base"); bad.flush()
            with self.assertRaises(egm.EngineError):
                egm.open(bad.name)

    def test_settings(self):
        with egm.Engine(settings={"RATE": 0.4}) as e:
            e.set("REFRESH", 0.02)
            with self.assertRaises(ValueError):
                e.set("NO_SUCH_SETTING", 1)


class TestExperimentalSettings(unittest.TestCase):
    """DEPTH, CHAIN, CONDITIONS and TREES through the SDK, on small worlds from tests/worlds.py (studies/ hold the full studies)."""

    @staticmethod
    def kb(lines, **settings):
        td = tempfile.mkdtemp(); path = os.path.join(td, "facts.txt")
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return egm.open(path, settings=settings)

    def test_depth_unlimited_reaches_further_without_errors(self):
        lines, hidden = worlds.remainders()
        got = {}
        for d in (4, 0):
            with self.kb(lines, DEPTH=d) as e:
                got[d] = {f.subject: f.object for f in e.infer_all() if f.relation == "has remainder"}
        right = {d: sum(got[d].get(a) == v for a, v in hidden.items()) for d in got}
        self.assertGreater(right[0], right[4])
        for d in got:
            self.assertEqual(sum(a in got[d] and got[d][a] != v for a, v in hidden.items()), 0)

    def test_chain_learns_three_step_rule(self):
        lines, unseen = worlds.lineage()
        with self.kb(lines) as e:   # CHAIN 2: a three-step relation cannot be expressed
            self.assertFalse(any(f.relation == "is great grandparent of" for f in e.infer_all()))
        with self.kb(lines, CHAIN=3) as e:
            got = {(f.subject, f.object) for f in e.infer_all() if f.relation == "is great grandparent of"}
            self.assertEqual(got, unseen)
            paths = e.rules(shape="path")
            self.assertTrue(paths and paths[0].premises == 3)
            self.assertEqual(e.experimental(), {"CHAIN": 3})
            f = [x for x in e.ask(f"{next(iter(unseen))[0]} is great grandparent of ?") if x.status == "inferred"][0]
            self.assertEqual(len(f.because), 3)

    def test_conditions_restrict_an_over_general_rule(self):
        lines, wrong = worlds.harvest()
        with self.kb(lines) as e:
            base = {(f.subject, f.object) for f in e.infer_all() if f.relation == "harvests"}
        with self.kb(lines, CONDITIONS=1) as e:
            cond = {(f.subject, f.object) for f in e.infer_all() if f.relation == "harvests"}
            rules = [r for r in e.rules() if r.condition]
        self.assertGreater(len(base & wrong), 100)          # the general rule fires for everyone
        self.assertEqual(len(cond & wrong), 0)              # the conditional rule only for farmers and miners
        self.assertTrue(rules and "works as" in rules[0].condition and "farmer" in rules[0].condition and "miner" in rules[0].condition)

    def test_trees_learn_gates(self):
        lines, hidden = worlds.gates()
        with self.kb(lines) as e:
            self.assertEqual(e.rules(shape="tree"), [])
        with self.kb(lines, TREES=1) as e:
            got = {f.subject: f.object for f in e.infer_all() if f.relation == "has value"}
            trees = e.rules(shape="tree")
            w = next(iter(hidden)); ans = [f for f in e.ask(f"{w} has value ?") if f.status == "inferred"]
        self.assertEqual(sum(got.get(w) == v for w, v in hidden.items()), len(hidden))
        self.assertTrue(trees and all(r.text.startswith("TREE ") and r.premises >= 3 for r in trees))
        self.assertTrue(ans and ans[0].rule.startswith("TREE ") and len(ans[0].because) >= 4)

    def test_experimental_settings_are_saved_and_announced(self):
        lines, hidden = worlds.gates(per_kind=120)
        td = tempfile.mkdtemp(); kb = os.path.join(td, "g.vtx")
        with self.kb(lines, TREES=1, DEPTH=0) as e:
            n = len(e.infer_all()); e.save(kb)
            self.assertTrue(any("experimental settings on: TREES=1" in l for l in e.cmd("RELATIONS")))
        with egm.open(kb) as e:
            self.assertEqual(e.experimental(), {"TREES": 1})
            self.assertEqual(e.config()["DEPTH"]["value"], 0)
            self.assertEqual(len(e.infer_all()), n)


class TestBinaryLookup(unittest.TestCase):
    def test_missing_binary(self):
        with self.assertRaises(egm.EngineNotFound):
            egm.find_binary("/nonexistent/voltex2")
        self.assertTrue(issubclass(egm.EngineNotFound, FileNotFoundError))


class TestParsersOnFixedText(unittest.TestCase):
    def test_padded_and_long_names(self):
        f = parse.fact_line("  a_very_long_subject_name_that_exceeds_the_column calls b stated")
        self.assertEqual((f.subject, f.relation, f.object, f.status), ("a_very_long_subject_name_that_exceeds_the_column", "calls", "b", "stated"))
        self.assertIsNone(parse.fact_line("  no stated or inferred answer"))
        self.assertIsNone(parse.fact_line("[INFER] 3 new facts"))

    def test_corrected_line(self):
        f = parse.fact_line("  x lives in y                    corrected: never held per census (t=1 revision 1 replaced by revision 2)")
        self.assertEqual((f.status, f.source), ("corrected", "census")); self.assertTrue(f.is_history)


class TestBench(unittest.TestCase):
    def test_reproduces_published_f1(self):
        key = json.load(open(os.path.join(EX, "tokenomics", "key.json")))
        with egm.open(M) as e:
            self.assertEqual(bench.score(key, bench.solve(e, key))["mean_f1"], 0.972)
            self.assertEqual(bench.score(key, bench.solve(e, key, strict=True))["mean_f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
