# Dynamic relational evolution in Voltex — pre-registration

Written before condition D, the generators and the harness are built, and before anything is run. Seeds 11–15 have never been used in any earlier study. v2.1, the AMEND prototype and the earlier declarative build are used unchanged as controls; their checksums are recorded in `controls_sha256.txt`.

## First-principles framing
An observation is a fact plus where it came from: which source, which record, the time it describes, which revision of that description, and whether it is a complete snapshot of the record or a partial update. "X lives in A" and later "X lives in B" are only a change if both describe the same record from the same source and the later one is a complete description. Without that context, the right behaviour is to keep both and not manufacture certainty.

Four distinctions are kept separate throughout:
- **evidence vs contradiction:** different values are a conflict only between independent sources, on a relation the engine has itself learned to be one-value;
- **lost proof vs falsehood:** a derived fact that loses its proof becomes underived, not false;
- **history vs current:** past observations stay queryable;
- **new evidence vs supersession:** only a newer complete snapshot of the same source and record removes facts.

## Conditions
| | Name | Binary | How an observation is expressed |
|---|---|---|---|
| A | DELETE/UPDATE | v2.1, unchanged | source-side diff: replaced one-value fact → `UPDATE`; removed → `RETRACT`; added → `INGEST` |
| B | procedural AMEND | AMEND prototype, unchanged (`EXPLAIN 2`, `SUSPECT 0`) | replaced → `AMEND` (`AMEND CORRECT` for a correction); removed → `RETRACT`; added → `INGEST` |
| C | evidence-only | v2.1, unchanged | every fact of every observation → `INGEST`; nothing else |
| D | source-aware evidence | new copy `evolve/voltex2_evo.cpp`, explained staleness off | `OBSERVE <source> <record> <time> <revision> <snapshot\|partial> \| fact ; fact …` |
| D-x | D + B's explained staleness | same binary, switch on | as D |
| P | earlier declarative amendment records | `declarative/voltex2_decl` with `DECLFN 1`, unchanged | replaced → new fact + `ev amends/replaces/sets` (+ `is correction`; + `follows` when a value returns); removed → nothing (no vocabulary for it); added → `INGEST` |

**Same information for every condition.** A source produces revisions in time order. The A/B/P translations are computed at the source from each revision and the one before it (in time order); C and D receive the observation as it is. Translations use the source schema's cardinality (one-value vs many), which a database or codebase knows. All conditions receive their inputs in the same arrival order, including out-of-order and duplicated deliveries. A partial update never produces a removal or a replacement in any condition. No condition sees the hidden truth.

## The new mechanism in D (every primitive and assumption)
1. **`OBSERVE` envelope (ingestion layer).** The facts are ingested as ordinary records (grammar and counts unchanged). The envelope (source, record key, time, revision, scope) is kept in an observation log, saved as a sidecar.
2. **Projection (evidence-management layer, run at each rebuild).** For each (source, record):
   - group observations by time; within a time, the highest revision wins (a later revision corrects an earlier one);
   - fold the times in ascending order: a snapshot sets the record's state, a partial adds to it.

   The current view is the union over sources of each record's latest state, plus any facts ingested without an envelope. Relations, rules and inference run unchanged on the current view.
3. **History.**
   - A fact that is not current but was in an earlier effective state is *historical* (it held per that source, until a time).
   - A fact that appeared only in a revision later corrected at the same time *never held* per that source.
4. **Neutral flags, never resolutions.**
   - **Sources disagree:** two different sources currently give different values for a subject in a relation the engine itself estimates as one-value (≥ 0.9 of subjects single-valued). Same-source multiple values are never flagged.
   - **Uncertain after a partial update:** a newer partial observation of the same record gives a different value in an estimated one-value relation. The earlier value is not removed; the subject is reported as uncertain.

   Neither flag deletes anything.
5. **Change signal.** Subjects of records whose state changed (plus one hop) feed v2.1's existing `touched` mechanism, which UPDATE already uses.
6. **D-x only:** the dependency trace and same-rule re-derivation from B, applied to facts that left a record's state.

Assumptions: record identity is the given key; time and revision order are given; scope is given; one-value status is learned statistically and used only for flags. No relation-specific rules.

## Worlds
| World | Content | Initial KB | Rules that hold |
|---|---|---|---|
| People | blind-world generator, scale 1, coverage 0.5, default noise | one snapshot per subject, source `census` | the generator's rules (e.g. lives in ∘ is located in ⇒ is from) |
| Database | employees, departments, managers, divisions, projects, clients | one snapshot per row, source `hr` | works in ∘ is managed by ⇒ reports to; works in ∘ is part of ⇒ belongs to |
| Code | modules and functions | one snapshot per function and module, source `repo` | calls ∘ is defined in ⇒ depends on |

**Probes.**
- **Current one-value:** right / wrong / ambiguous (several unflagged values) / abstain (flagged or no answer).
- **Current set:** right if the unflagged current set equals the truth.
- **Fact asserted?** right / wrong / abstain.
- **Held:** current / past / never; "cannot answer" counts as abstain.
- **Conflict:** flagged or not.

## Scenarios (dataset types 1–12)
| Code | World | Type | What happens | Truth |
|---|---|---|---|---|
| ch | people | 1, 10 | snapshot t2: lives in B (new region), is from updated if stated | B; new region; A held in the past |
| stale | people | 10 | snapshot t2: lives in B, the stated is from left unchanged by the source | is from = new region |
| samereg | people | 11 | snapshot t2: lives in C in the same region; is from unchanged (still true) | is from unchanged |
| multi | people | 2 | snapshot t2 lists two residences, A and C | both current, no conflict |
| corr | people | 3 | t1 revision 2 corrects a wrong lives in / works as | corrected value; old value never held |
| src | people | 4 | source `survey`, partial: lives in C | conflict should be flagged (census is right) |
| compat | people | 4, 12 | source `survey`, partial: X knows Y (new), X volunteers at S (a new relation) | compatible; nothing flagged; facts present |
| miss | people | 7 | move to a settlement whose region is not observed | is from: abstain (not the old region) |
| part1 | people | 8 | partial t2: works as F (truth: job changed) | not wrong: right or abstain |
| part2 | people | 7, 8 | partial t2 that omits X's other facts | omitted facts still current |
| ooo | people | 9 | snapshots t2 (B) and t3 (C) arrive as t3, t2, t3 again | C; B held in the past |
| vol | people | 12 | partial t2: volunteers at S1; partial t3: volunteers at S2 | both current, no conflict |
| db_move | database | 5, 1 | employee row t2: works in d2 (reports to updated if stated) | d2; new manager |
| db_mgr | database | 10 | department row t2: new manager; employee rows unchanged (stale reports to) | employees report to the new manager |
| db_proj | database | 2, 8 | employee row t2: one project removed, one added | new project set |
| db_corr | database | 3 | revision 2 at t1 corrects the department | corrected; old never held |
| db_src | database | 4 | source `payroll`, partial: a different department | flagged |
| db_ooo | database | 9 | d1→d2 (t2) →d3 (t3), arriving t3, t2, t3 | d3 |
| code_keep | code | 11 | f calls g and k (both in M1); a commit drops g | f depends on M1 still |
| code_drop | code | 6, 10 | f's only call into M2 is dropped; the manifest is updated in the same snapshot | f does not depend on M2 |
| code_move | code | 6, 10 | g moves M1→M3; callers' manifests not updated | callers depend on M3, and on M1 only if another path exists |
| code_add | code | 6, 1 | a new function h in a new module M9; f now calls h | f depends on M9 (new relationship) |
| code_ooo | code | 9 | g's moves t2 and t3 arrive out of order | latest module |

About 15 instances per scenario per seed, on disjoint subjects, seeds 11–15.

## Hypotheses and decision rule
- **H1 (C, evidence-only).**
  - On ch / ooo / db_move / code_drop, C keeps the old value current in ≥ 95% of probes.
  - C flags 0 false contradictions.
  - C cannot separate history from current state.
- **H2 (equivalence of P and B; FU2 confirmation).**
  - **Per-probe agreement:** P and B give the same answer on ≥ 95% of probes in the scenarios both can express (ch, stale, corr, ooo excluded, db_move, db_corr).
  - **FU2 confirmation:** the earlier study's scale and scenario sessions, re-run unchanged on seeds 11–15 with B and C2fn. C2fn must be ≥ 95% right on every scenario's current and held probes, and within 2 points of B on every scale measure.
- **H3 (P's hidden assumptions).** Predicted from P's code:
  - multi: false contradictions ≥ 50%;
  - db_proj: P cannot remove the dropped project (wrong ≥ 95%).
- **H4 (D).**
  - ≥ 95% right on: ch, corr (current and never-held), ooo, db_move, db_corr, db_ooo, code_drop, code_add, db_proj, code_ooo.
  - Every condition other than C must reach ≥ 95% on ch.
  - **False contradictions ≤ 5%** on multi, compat and vol.
  - **Conflicts flagged ≥ 90%** on src and db_src.
  - **Partial updates:** part1 is never wrong (≥ 95% right or abstain); part2 keeps ≥ 95% of the omitted facts.
- **H5 (derived and stale conclusions).**
  - Derived-only conclusions follow their premises in A, B, D, D-x and P (≥ 95% right when derivable); C fails.
  - Stale stated fields (stale, db_mgr, code_move): report each condition. Prediction: B, P and D-x beat A and D; C is worst.
- **H6 (loss of proof ≠ negation).**
  - code_keep: every condition except C keeps "depends on M1" ≥ 95%.
  - samereg, predicted from reading B's code: when the same rule re-derives the same value, B, P and D-x report "current value unknown" for a still-true stated fact in ≥ 50% of cases; A, C and D keep it ≥ 95%.
- **H7 (no regression).**
  - With no envelopes, D's output is byte-identical to v2.1 on the existing gate files.
  - Ordinary rule discovery after updates (true rules accepted, decoys) stays within 1 of each world's no-update run, for every condition.
- **H8 (cost and scaling).**
  - People world at scale 1, 2, 4 × 50, 200, 800 updates; batch (query once at the end) and interactive (query after every update, for 50 updates). Timeout 900 s.
  - Prediction: in batch, D is at most 1.5× P's time and faster than B at every size.

**Decision.**
- If C meets the H4 targets, choose C (evidence-only).
- Otherwise choose D if it meets H4 and H7, and recommend its mechanism (envelope + projection) as the smallest addition.
- Add D-x's explained staleness only if it gains ≥ 10 points on stale fields and causes ≤ 5% false "unknown" on samereg.
- Keep B (AMEND) only for a probe class where it beats D by ≥ 10 points that D cannot reach.
- Keep A's destructive operations for removal by policy, regardless of these results.
- A hybrid is reported if the results split.

Results that fail are reported as failures; nothing is tuned on hidden results. Exploratory work is labelled separately.
