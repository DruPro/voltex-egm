# Depth study: results

Pre-registration: PREREGISTRATION.md (sha256 201e00ad…, 2026-11-20T16:15:43Z).
Deviations: DEVIATIONS.md (two harness fixes; neither changes what is measured).
Gate: DEPTH default (4) byte-identical to shipped 2.2.1 on 22/22 datasets.

| Prediction | Result | Verdict |
|---|---|---|
| D1 remainders: 208/225 correct, 0 wrong, 17 stay blank | 208/225 correct (was 192), 0 wrong | Pass |
| D2 divisibility unchanged | 319/319 derivable inferred at both depths, 0 wrong | Pass |
| D3 blind world: recall does not fall; precision falls ≤ 0.02 | Precision 0.9545 → 0.9544; recall 0.4894 → 0.4898 | Pass |
| D4 cost (exploratory) | Fixpoint reached in 4–7 rounds (median 5); inference ≤ 153 ms | Reported |

D3 detail (15 runs, 5 seeds × 30/50/70% coverage): running to fixpoint derived 43 more facts
in total (36,014 vs 35,971), of which 4 were wrong (39 of 43 correct, 91%). All 4 came from
one run (s0_c30). In 9 of 15 runs the extra rounds derived nothing.

Conclusions:
- The 4-round cap only binds on long chains through a base relation (remainders). In the
  18-relation hidden world, inference converges naturally in at most 7 rounds.
- Removing the cap did not open a path for decoy or tendency rules to compound errors here:
  precision is unchanged to three decimals. A per-tier depth policy is not needed for this
  world; it remains a hypothesis to test on noisier data.
- Recommendation: ship `SET DEPTH` (0 = fixpoint) now; make fixpoint the default only after
  it passes the same check on the remaining test worlds, since changing the default changes
  published outputs.
