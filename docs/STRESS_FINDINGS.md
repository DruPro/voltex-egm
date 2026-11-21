# What the engine found in real code and real data

Source: the stress study, `studies/stress`:
- **31 datasets, 295 runs:** four code corpora of 254,000-400,000 source lines each, four real system tables, and
  synthetic shapes.
- **Hidden key:** 20% of every real dataset was hidden from the engine as an answer key.
- **Files:** charts and full proof trees are in `studies/stress/report/index.html`; raw results in
  `studies/stress/explore/`.

These are exploratory findings with no pre-registered verdicts. The infra verdicts are in
`studies/stress/RESULTS.md`.

For the case the engine is built for (exact facts, complete truth, one large codebase), see `docs/STRENGTHS.md`.

## Unicode: rules the tables imply, and the exceptions they hide

The input was 29,948 facts about 11,172 characters: category, bidi class, script, case partners and decomposition.
No rule was given. The engine learned these, among others:

| Rule | Agreement where known | Cases |
|---|---|---|
| x has uppercase y ⇒ y has lowercase x | 0.98 | 589 |
| x has uppercase y, y is in script s ⇒ x is in script s | 0.98 | 471 |
| x has uppercase y, y has bidi class b ⇒ x has bidi class b | 1.00 | 490 |
| x decomposes to y, y has category c ⇒ x has category c | 0.96 | 477 |

- **Accuracy:** against Python's `unicodedata`, **1,281 of 1,331 new facts are true (96.2%)**. The hidden key alone
  suggested 0.83, because it can't score facts outside the extracted range.
- **Characters it never saw:** 178 derived facts are about characters outside the extracted range, reached through a
  stated case partner, and 177 of them are true.
- **The errors are mostly Unicode's exceptions.** 40 of the 50 fall on characters that break the rule by design:
  - 30 Greek letters with iota subscript (titlecase capitals, two-character uppercase);
  - 6 one-way case pairs (the Kelvin, Ohm and Ångström signs, ß, the theta symbol, Cyrillic monograph uk);
  - 4 Balinese and combining vowel signs.

  The other 10 come from the extractor, which takes the script from the first word of a character's name.

```
ⓝ Circled Latin Small Letter N  has bidi class L                     [law]
├── ⓝ has uppercase Ⓝ                                               [law: inverse of a stated fact]
│   └── Ⓝ Circled Latin Capital Letter N has lowercase ⓝ            (stated)
└── Ⓝ has bidi class L                                               (stated)
```

## Real Python code: call locality, and a category error

The input was 64,763 facts from 125 installed packages, extracted by `egm extract python` with calls resolved across
modules. The run used `COVERAGE 0` and a sized `MAXWORDS`.

- **Learned:**
  - `a calls b, b is defined in m ⇒ a is defined in m` (tendency, 0.82 on 10,372 cases);
  - nested definitions are transitive (law, 0.97 on 798).
- **Answers come with multi-step proofs:**

```
numpy _block_slicing  is defined in numpy._core.shape_base           [tendency]
├── _block_slicing calls _block_info_recursion                       (stated)
└── _block_info_recursion is defined in shape_base                   [tendency]
    ├── _block_info_recursion calls atleast_nd                       (stated)
    └── atleast_nd is defined in shape_base                          (stated)
```

- **The failure:** `a is defined in m, m imports n ⇒ a imports n` agrees on 80 known cases out of 98,782, and
  produces 100,859 of the 108,323 derived facts. That is a category error, because imports belong to modules, not
  functions. Overall, 1,783 derived facts were in the hidden key.
- **`TENDENCYSTEPS 0`** removes that rule, but also call locality: 73 facts are left.
- **`CONDITIONS 1`** (in the bench, on a different extraction) raised precision from 0.01 to 0.88.

## dpkg: depth decides between useful and a flood

The input was 14,296 facts about 2,053 installed packages. Truth for `depends on` is the full transitive closure of
Depends and Pre-Depends.

| `DEPTH` | Derived facts | True |
|---|---|---|
| 1 | 13,000 | 87.6% |
| 2 | 60,537 | 50.9% |
| 4 (default) | 1,151,048 | 4.2% |

- **Growth:** new facts per round were 12,324, 47,406, 214,632 and 875,868.
- **Cause:** two law-tier rules, the reversed `recommends(a,b) ⇒ depends on(b,a)` (agreement 0.15) and the
  transitivity of `depends on` (0.27).
- **Settings:** because all of it is law tier, `TENDENCYSTEPS 0` changes nothing. With `DEPTH 0` the engine runs out
  of memory after 340 s.

## Settings are per dataset

| Dataset | Default P / R | With `TENDENCYSTEPS 0` |
|---|---|---|
| Python packages | 0.010 / 0.067 | 0.963 / 0.067 |
| Company ×8 | 1.000 / 0.956 | 1.000 / 0.491 |
| Company, 15% noise | 1.000 / 0.648 | 1.000 / 0.217 |
| Hidden world | 0.974 / 0.437 | 0.999 / 0.400 |

More settings, by case: `docs/CHOOSING_SETTINGS.md`.

## Extractor artifacts (check yours)

Some "discoveries" were made true by how the facts were extracted:
- **The bench's own code layer** records only same-module calls, so call locality holds at 1.00 by construction.
- **Its C layer** records fields only for structs, so "has a field ⇒ is a struct" is true by construction too.
- **`egm extract python` gives a module and a function in it the same name.** `cloudinit__subp` is both the module
  and its function `subp()`. 6 names collide, and 62 facts read "X is defined in X".
