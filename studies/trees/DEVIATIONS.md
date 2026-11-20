# Deviations

- D1 (performance only, after T7 measured a 460x slowdown). The tree candidate search was
  rewritten: anchor features computed once per entity and cached; supports counted with
  integer keys; triples built only from frequent pairs (the same filter previously applied
  afterwards). Candidate order is rebuilt exactly as before. Verified byte-identical output
  against the original implementation's logs on 25 runs (5 gate worlds, 5 adder worlds,
  15 hidden-world runs) and identical facts, accepted rules and conflicts on the 4
  company-world datasets. Rule mining on the largest hidden-world file: 56 s -> about 9 s.
  All reported results come from the original implementation's runs.
