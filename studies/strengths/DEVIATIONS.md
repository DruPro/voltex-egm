# Deviations

## 1. Round 2: the same code facts, stated in the engine's rule language (after round 1)

Round 1 ran as registered; its results are in `results/`, and its verdicts are in RESULTS.md. Two of its targets
could not be expressed by the engine's rule shapes:
- **Inverse, composition, transitive, plus paths with `CHAIN` and trees with `TREES`.** There is no same-direction
  copy `r(a,b) ⇒ s(a,b)`, so "a direct base is an ancestor" was unlearnable. A hidden class could only reach
  ancestors through a stated parent, and recall on `is a subclass of` stopped at 0.30 at every `DEPTH`.
- **`binds` had no anchor for a tree.** Trees join branches at an entity one step from the fact's subject, like a gate
  linked to its output wire, and constants can't be reached by composition. Nothing was learned for `binds`.

**Round 2 (`tools/extract.py --r2`, `obs_r2/`, `results_r2/`)** adds two fact families, both read from the same ast
nodes:
- `B is a base of C`, the parent-side view of `C inherits from B`;
- `F__a0 is first argument of F`.

The target `F binds v` becomes `F__a0 is bound to v`. The code, the hidden subjects (seed 11, the same 5,901 facts)
and the truth are unchanged. `MAXWORDS` becomes 28,500 for the 27,398-word vocabulary, by the same sizing rule.
`PREREGISTRATION_R2.md` fixes the round 2 runs and predictions before it runs.

## 2. Round 3: the guide's setting for exact data (after round 2)

In round 2, every law-tier rule was exactly true of Python. All the wrong facts came from tendency-tier rules, for
example "an ancestor is a direct base" (agreement 0.68) and "a class is in its base's module" (0.57).
`docs/CHOOSING_SETTINGS.md` (committed before this study, 43df294) says to use `TENDENCYSTEPS 0` for answers you act
on without checking. Round 3 reruns round 2's seven runs with that setting added, and changes nothing else. It is
pre-registered in `PREREGISTRATION_R3.md`.
