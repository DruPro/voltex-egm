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
        self.assertEqual(run(text, "fresh")["actions"][0]["tape"], run(text, "rebuild")["actions"][0]["tape"])


if __name__ == "__main__":
    unittest.main()
