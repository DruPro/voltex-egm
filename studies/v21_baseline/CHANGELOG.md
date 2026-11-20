# Voltex v2.1

Five changes, each adopted only after a controlled experiment against the frozen v2.0
(evidence: "Voltex Improvement Experiments: Findings and Decisions").

| Change | Default | Turn off | Evidence |
| --- | --- | --- | --- |
| Coverage-aware rule acceptance (lower-only) | on | `SET COVERAGE 0` | Recall on derivable facts at 30% coverage 0.07 -> 0.94, precision 0.87 -> 0.99; unchanged elsewhere |
| Confidence labels (law / tendency) on rules and derived facts | on | `SET LABELS 0` | Law-labelled facts 99.3-99.8% correct, ~85% of all inferences |
| Contradictions need two distinct rules to agree | on | `SET CORROBORATE 0` | False flags -80 to -90%; company-world detection unchanged |
| `RETRACT <fact>` and `UPDATE <fact>` | always available | (unused = inert) | Retraction exactly equals never-ingested (5/5 worlds); 150/150 homes updated |
| Staleness check after `UPDATE` (needs labels) | on | `SET STALE 0` | 31/31 detectable stale facts flagged, 51/52 flags truly stale |

All four switches off reproduces v2.0 output byte for byte (gate A, 22/22 datasets).
Defaults reproduce the experimentally validated configuration (gate B, 21/21 datasets).

Output changes when labels are on:
- `INFER ALL` lines gain a third column: `FACT<TAB>fact<TAB>law|tendency`
- `ASK` and `INFER` show `[law]` or `[tendency]` on inferred facts
- `RELATIONS` prints a `[COVERAGE]` line and `cov= rel= tier=` per rule

Not included (rejected or deferred by evidence): two-sided coverage threshold, conditional-rule
representativeness check, law-only contradiction voting, deferred rule refresh, richer rules,
multi-part facts.

Known limitations carried over:
- Ties between equally supported values are resolved by internal word order (reporting ties is a candidate change, untested).
- Retracted records remain as tombstones in the compressed store (no compaction yet).
- UPDATE scans all records; it refuses relations that hold several values per subject (use RETRACT there).
- Full rebuild after each new fact: ~2.6 s per ingest+ask at 33k facts (incremental inference deferred).

Verify: `./gates.sh` (equivalence) and `./voltex2 --selftest`.
