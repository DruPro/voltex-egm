# Stress bench and C1 (cheaper category pair loop): results

Plan: `PREREGISTRATION.md` (hash in `prereg_hash.txt`). Deviation: `DEVIATIONS.md` 1, a bench bug that put the
knowledge base's temp path in the compared output. It was fixed and the affected cells were rerun on both binaries.

Runs (git-ignored, `runs/`): base and c1 timed runs, `base_s`/`c1_s` hash reruns. Gate results:
`results_gate_stress_C1_default.json`, `results_gate_stress_C1_cs0.json`. Base = HEAD build, C1 = `lab/voltex2_c1.cpp`.

## Verdicts

| ID | Claim | Verdict |
|---|---|---|
| H1 | Identical output on every comparable bench cell | **PASS**: 294 of 294; 1 cell not comparable (`world_packages\|depth0`: both binaries exceeded the 12 GB cap) |
| H2 | Regression gate | **PASS**: 221/221 with defaults, 221/221 with `CLUSTERSTREAM=0` on C1 |
| H3 | No cell slower by more than 10% + 0.3 s | **PASS**: none |
| H4 | At least 1.5× faster on 4 large-vocabulary cells | **FAIL** (3 of 4): gates 2,400 22.14 → 2.40 s (9.2×); zipf big 9.32 → 1.90 s (4.9×); code mixed 10.62 → 3.90 s (2.7×); clusters big 45.08 → 34.46 s (1.31×) |
| H5 | No peak memory increase beyond 5% + 5 MB | **PASS**: none |
| H6 | `make test` and `make sanitize` | **PASS**: 30/30 kit checks, 63/63 tests, both builds |

**Decision (as pre-registered):** H1, H2, H3, H5 and H6 pass, so C1 replaces the loop in `src/voltex2.cpp` with no new
setting. The whole bench went from 1,850 s to 1,670 s.

**Why H4 failed on clusters.** That dataset has 400 vocabularies that share no context. The pairs left after the
joined check really are in different categories, so each needs a full similarity test, and C1 doesn't make those
cheaper. It is the one shape where an index over shared contexts could help, because there is no hub context. That is
an exploratory lead, not tested.

## Item 2 as written: rejected before the plan (exploratory)

Only comparing words that share a context skips nothing on these worlds. On gates, company and real code, 77-100% of
words reach the similarity threshold only through one hub context, such as the start of a record. An exact
prefix-filter index would visit more pairs than the current loop. The real cost was the joined check, which C1 fixes.

## The bench (descriptive, base binary)

31 datasets, 295 cells. Every cell completed except one, which hit the memory cap.

- **Real code**, with 20% of the facts held out:
  - Python stdlib: 275,604 lines;
  - Debian Python packages: 400,383 lines;
  - C headers: 400,142 lines;
  - JS: 254,235 lines;
  - all three languages in one engine.
- **Real tables:** dpkg, Unicode, tz and services, plus all of them together.
- **9 new synthetic shapes.**
- **12 existing generator worlds.**

Default settings, or `MAXWORDS` sized to the vocabulary where it passes 11,000 words:

| Dataset | Facts | Full s | Peak MB | Update/full time | Precision | Recall |
|---|---|---|---|---|---|---|
| code_py_stdlib | 18,457 | 1.3 | 22 | 1.31 | 1.000 | 0.084 |
| code_py_dist | 23,157 | 2.4 | 53 | 1.33 | 0.010 | 0.067 |
| code_c_headers | 13,769 | 0.8 | 18 | 1.25 | 0.046 | 0.009 |
| code_js | 10,161 | 0.8 | 16 | 1.25 | (none derived) | 0.000 |
| code_mixed | 42,446 | 10.6 | 61 | 1.35 | 0.015 | 0.041 |
| world_packages | 14,296 | 96.8 | 3,058 | 0.73 | 0.002 | 0.460 |
| world_unicode | 29,948 | 1.7 | 34 | 1.29 | 0.830 | 0.145 |
| world_mixed | 45,738 | 96.6 | 3,239 | 1.49 | 0.002 | 0.245 |
| gen_company32 | 122,042 | 12.1 | 130 | 1.33 | 1.000 | 0.957 |
| gen_gates2400 | 80,063 | 22.1 | 96 | 1.45 | (none derived) | 0.000 |
| synth_clusters_big | 79,598 | 45.1 | 92 | 1.45 | (no key) | |
| synth_social | 7,206 | 0.2 | 16 | 1.50 | 1.000 | 1.000 |

Findings for the owner. These are about the engine's decisions, not the infra, so they are reported only:

- **Python package code: precision 0.010 with defaults, 0.963 with `TENDENCYSTEPS 0`** (same recall, 0.067). This
  matches the earlier realcode finding on a second corpus.
- **dpkg derives 1.15 million facts from 14,296** (59 s and 3.1 GB, nearly all of it in `INFER ALL`). A rule accepted
  with 2% agreement chains the package graph. Precision against the key undercounts here, because many derived facts
  are true indirect dependencies and the key holds only direct ones.
- **With `DEPTH 0`, dpkg exhausts memory.** The engine dies with an uncaught `std::bad_alloc` after 340 s instead of
  stopping with a `[LIMIT]` message. A memory guard is an infra fix; which rules fire is not.
- **Updates cost a full rebuild.** The update script (90%, then 5%, then 5%, a query after each) cost 1.0-1.5× a
  single full build on every dataset, because each batch brings new names. This is the measured input for item 3.
- **Default settings derive nothing** on gates, lineage, JS, multi-word names, zipf hubs and time zones, and 46 facts
  on services, all wrong against the key. Gates and
  lineage are expected, since they need `TREES` or `CHAIN 3`.
