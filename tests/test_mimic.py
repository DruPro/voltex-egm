"""Mimic (lang/mimic): a language whose operations are learned from examples. Fast checks of its contract."""
import os, sys, unittest
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "lang", "mimic"))
import mimic  # noqa: E402

AND_NOT = """function and
  0 0 -> 0
  0 1 -> 0
  1 0 -> 0
  1 1 -> 1
end
function not
  0 -> 1
  1 -> 0
end
circuit nand a b -> out
  t = and a b
  out = not t
end
"""
INC = """machine inc
  start carry
  blank _
  carry 1 -> 0 left carry
  carry 0 -> 1 left halt
  %s carry _ -> 1 left halt
end
"""


def run(text, mode="fresh"):
    return mimic.execute(text, mode=mode, out=lambda s: None)


class TestMimic(unittest.TestCase):
    def test_learned_gates_compute(self):
        log = run(AND_NOT + "".join(f"eval nand {a} {b}\n" for a in "01" for b in "01"))
        self.assertEqual([x["result"]["out"] for x in log["actions"]], ["1", "1", "1", "0"])
        self.assertEqual(log["learned"]["and"]["learned"], 4)

    def test_machine_runs_and_constant_is_declared(self):
        log = run(INC % "" + "run inc on 1011\nrun inc on 111\n")
        a, b = log["actions"]
        self.assertEqual((a["tape"], a["status"], b["tape"]), ("1100", "halted", "1000"))
        self.assertEqual(a["declared"], ["move"])            # always left: applied as declared, not inferred

    def test_untaught_transition_stops_unknown(self):
        log = run(INC % "?" + "run inc on 111\nrun inc on 1011\n")
        a, b = log["actions"]
        self.assertEqual(a["status"], "unknown"); self.assertEqual(a["symbol"], "_")
        self.assertEqual(b["status"], "halted")              # doesn't need the untaught row
        self.assertEqual(log["learned"]["inc"]["hidden"]["carry _"]["inferred"], "? left ?")

    def test_value_limit_is_reported(self):
        rows = "".join(f"  {i} -> {i}\n" for i in "0123456789")
        with self.assertRaises(mimic.MimicError):
            run(f"function wide\n{rows}end\n")

    def test_parse_errors_name_the_line(self):
        with self.assertRaisesRegex(mimic.MimicError, "line 2"):
            mimic.Program.parse("function f\n  0 1 => 1\nend\n")

    def test_modes_agree(self):
        text = INC % "" + "run inc on 1111\n"
        tapes = {m: run(text, m)["actions"][0]["tape"] for m in ("fresh", "rebuild", "refresh")}
        self.assertEqual(len(set(tapes.values())), 1, tapes)

    def test_refresh_mode_circuit_and_unknown(self):
        """refresh mode reuses names and swaps state; it must compute and abstain exactly as fresh does."""
        text = AND_NOT + "".join(f"eval nand {a} {b}\n" for a in "01" for b in "01")
        self.assertEqual([x["result"]["out"] for x in run(text, "refresh")["actions"]], ["1", "1", "1", "0"])
        a = run(INC % "?" + "run inc on 111\n", "refresh")["actions"][0]
        self.assertEqual((a["status"], a["symbol"]), ("unknown", "_"))


class TestMimicIsolation(unittest.TestCase):
    def test_machine_next_to_a_function_learns_every_row(self):
        """A machine taught next to a function that shares 0/1 must keep its blank-symbol row (machine values are
        namespaced; without that the engine's categories dropped the 64 `reads _` facts from the relation)."""
        log = run("function not\n  0 -> 1\n  1 -> 0\nend\n" + INC % "" + "run inc on 111\n")
        self.assertEqual(log["learned"]["inc"]["learned"], 3)
        self.assertEqual(log["actions"][0]["tape"], "1000")


class TestPlayground(unittest.TestCase):
    def test_tour_runs_and_shows_learning(self):
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(ROOT, "lang", "mimic", "play.py"), "--tour", "--fast", "--no-color"],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        for want in ("4 of 4 rows learned", "halted after 14 steps", "UNKNOWN", "sum = 1, carry = 1"):
            self.assertIn(want, r.stdout)


if __name__ == "__main__":
    unittest.main()
