# Deviations and fixed implementation parameters

Fixed before any run (implementation limits, not tuned on results):
- Path-rule search: at most 50,000 path steps explored per start entity; at most 200 candidate
  paths per target relation, ranked by how many stated target pairs they connect.
- Inference over path rules: at most 10,000 paths followed per start entity per round.
- With CHAIN > 2 or CONDITIONS 1, the REFRESH rule cache is bypassed (full rebuild), because
  cached rules do not record path or condition relations.
- Staleness tracing (STALE / computeDeps) covers the shipped rule shapes only, not path rules.

Found during smoke testing, before any experiment run (containment world, which is also an H5
world; the fix was not tuned to results):
- D1. Path rules allowed chains that revisit an entity (A is in B, B contains A, A knows D =>
  A knows D), which makes a rule partly tautological; 15 rules were accepted on the containment
  world instead of 3, including "is in & contains & knows => knows". The shipped two-premise
  rules already forbid returning to the start (c != a). Fix: path rules use simple paths only
  (no entity repeated) in mining, scoring and inference: the direct generalization of the
  shipped constraint.
Round 2 implemented per PREREGISTRATION_R2.md (F1, F2). Round-1 binary kept as voltex2_r1.
