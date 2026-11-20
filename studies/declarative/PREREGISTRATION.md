# Declarative amendments through evidence ingestion — pre-registration

Written after reading the v2.1 source and before building or running condition C.
Independent of the earlier amendment study: v2.1 (`v21/voltex2.cpp`) and the AMEND prototype (`amend/voltex2_amend.cpp`) are used unchanged as controls.

## Architecture findings that shape the design (from reading the code)
1. Ingestion is append-only. A repeated record only increments its count.
2. Relations are sets of (subject, object) pairs built from records. Record counts never reach relations or rules, so repeating evidence cannot outweigh older evidence.
3. A template becomes a relation only with ≥ 3 supporting records, and a word can fill a slot only if the learned word classes put it in a class of size ≥ 2. Only the 40 largest relations are kept.
4. Inference only adds derived facts and conflict flags. It never removes or demotes a stated fact. For a one-value relation, a stated value is only *flagged* when ≥ 2 distinct rules agree on another value (or one law-tier rule after UPDATE).
5. The rule language is positive: inverse and two-premise composition. It has no negation, no time and no single-premise implication.

## Conditions
- **A: DELETE/UPDATE.** v2.1 binary unchanged. Changes use `UPDATE`; new facts use `INGEST`.
- **B: procedural AMEND.** AMEND prototype binary unchanged, `SET EXPLAIN 2` (same-rule re-derivation, V2b), `SET SUSPECT 0`. Uses `AMEND`, `AMEND CORRECT`, `HISTORY`, `WAS`.
- **C: declarative.** A new isolated copy (`declarative/voltex2_decl.cpp`) that receives only `INGEST`, never AMEND/UPDATE/RETRACT. Two sub-variants:
  - **C1:** amendment records also take part in ordinary relation and rule building.
  - **C2:** amendment records are stored, counted and saved like any record, but excluded from relation/rule building.

## Declarative representation (condition C)
One amendment event, with a fresh id `ev…` (letters only), is ordinary records:
```
X lives in B          the new fact
ev amends X           which subject
ev replaces A         the earlier value
ev sets B             the new value
ev is correction      only for corrections (absent = change)
ev follows ev0        only where order cannot be read from the values (a value returns)
```
A withdrawal is one record: `ew withdraws ev`.
The amended *relation* is not named. It is identified from the evidence: the one-value relation that holds both (X, B) and (X, A).

## Minimal extension (C), stated in advance with its reason
Findings 2, 4 and 5 mean ordinary inference cannot make a stated fact stop being current. Something must read the amendment evidence and decide which stated facts are superseded. The extension is one interpretation step, run at every model rebuild. It is a pure function of the stored records, with no imperative command:
1. Collect events from live records of the form `<id> amends|replaces|sets|is|follows|withdraws <value>`. An event needs amends, replaces and sets. Withdrawn events are inactive.
2. Resolve each active event to the one-value relation (≥ 0.9 of subjects single-valued, not counting subjects that have events) that contains (X, new). If none or several match, the event is unresolved and reported.
3. Order the events for each (relation, subject) by `follows` records, else by value chain (an event whose old value is another's new value comes later). The current value is the last event's new value. If the order cannot be determined, the current value is unknown.
4. Superseded facts leave the stated view and are kept with provenance (event, change/correction, replaced by). A fact set only by withdrawn events is marked withdrawn and leaves the view.
5. For parity with B, the same downstream handling is applied to the superseded facts: changed subjects are marked touched, the dependency trace runs, and same-rule re-derivation with "unknown" applies (the B/V2b logic).
6. A one-value relation subject with ≥ 2 stated values and no active event is reported as a CONTRADICTION, and its current value is unknown. This step is not specific to declarative amendments and could be ported to A or B; it is scored but not credited as a declarative advantage.

## Data
Blind-world generator (`blind/hidden/world.py`), scale 1, coverage 0.5, default noise (3% wrong, 1% added contradictions), seeds 1–5. Voltex never sees the hidden truth.

**S1, scale session.** 15% of eligible people move (same mover selection as the earlier study). In addition, 3 settlements per seed change region; their residents do not move, and no mover leaves from or arrives at them. Moves come first, then region changes.

**S2, scenario session.** A fresh ingest per seed, with disjoint subjects and up to 20 instances per type:
- **B1 change.** A correct `lives in` value A changes to B.
- **B2 correction.** A noise-wrong `lives in`/`works as` value A is corrected to the true value B.
- **D1 successive.** A→B, then B→C, in order.
- **D2 out of order.** B→C arrives before A→B.
- **D3 duplicate.** The A→B event arrives twice.
- **E contradiction.** A plain `X lives in B` arrives with no amendment (truth: still A).
- **F1 withdrawal.** A→B is recorded, then withdrawn (it was entered in error).
  - A: `UPDATE B`, then `UPDATE A`.
  - B: `AMEND B`, then `AMEND CORRECT A`.
  - C: event, then `withdraws`.
- **F2 revert.** A→B is real, then B→A is real. C gets `follows`.

**Order and probes.** Events arrive in each condition's natural form, in the same order. All probes are ordinary queries.
- **Current value:** `ASK X <rel> ?`
- **"Did X ever have V?":**
  - A: no history query, so scored "cannot answer".
  - B: `WAS`.
  - C: superseded/withdrawn lines of the same `ASK`.

## Metrics
Right, wrong and abstain are always reported separately.
- **S1 movers:**
  - P1 current residence;
  - P2 stale stated `is from` (answer = the flagged alternative / "unknown" / the stated value);
  - P3 previous residence.
- **S1 non-movers:** P4 stated `is from` and `lives in` (false conclusions).
- **S1 region changes:**
  - P5 settlement's current region;
  - P5r residents' `is from`, split into stated-stale and derived-only;
  - P5c stale inverse `R_old contains S` still asserted;
  - P6 previous region.
- **S1 rules:** P7 true expressible rules accepted, decoys accepted, accepted rules that mention amendment vocabulary.
- **Persistence (P8):** SAVE, LOAD, re-ask the S1 probe set, and compare the answers.
- **Cost:**
  - session wall time, median of 3 runs;
  - SAVE bytes (+ B's sidecar);
  - records and bytes per amendment;
  - operations per amendment.
- **S2:** for each scenario, current-value and held-value answers scored against the truth (yes-current / yes-past / never / unknown), plus the history count for D3.

## Hypotheses and decision rules
- **H1 (pure ingestion is insufficient).** With no extension (the C build with interpretation off), each of these leaves A as a stated current value for ≥ 95% of S1 movers:
  - (P0) the plain new fact;
  - (P1) the new fact ingested 5×;
  - (P2) the new fact plus `X formerly lived in A`.

  If this prediction fails, C uses the representation that worked instead of the extension.
- **H2 (parity).** In S1, C2 is within 2 points of B, averaged over seeds, on:
  - P1;
  - P2 right and P2 wrong;
  - P3;
  - P4;
  - P5;
  - P5r right and P5r wrong.
- **H3 (order and duplicates).**
  - D2 current value: C ≥ 95% right, A and B ≤ 5% (predicted).
  - D3: every condition's current value ≥ 95% right; B and C each record exactly one amendment ≥ 95% of the time.
- **H4 (contradiction ≠ supersession).** In E, C flags ≥ 95% and never reports B as the only current value; A and B flag ≤ 5%.
- **H5 (withdrawal and revert).** B and C answer held(B) = never in F1 and held(B) = yes-past in F2, each ≥ 95%.
- **H6 (change vs correction).** B and C answer held(A) = yes-past in B1 and never in B2, each ≥ 95%. A cannot answer.
- **H7 (contamination).** C1 contaminates if it accepts any rule that mentions amendment vocabulary, if its true or decoy rule counts differ from C2's, or if any S1 accuracy differs from C2's by > 2 points.
- **H8 (persistence).** Re-asked answers are identical after SAVE/LOAD for every condition (100%).
- **H9 (cost).** C's S1 session time ≤ B's (predicted, since C rebuilds once instead of once per amendment). Storage is reported as a ratio, with no threshold.

**Decision.**
- **Retain B (or A):** if H2 fails.
- **Adopt C:** if H2 holds and C wins at least one of H3, H5 or H9, and loses none of H2–H9. C2 is required if H7 finds contamination.
- **Hybrid:** if C wins some and loses some.
- **Contradiction-only win:** if C's only win is H4, the decision is a hybrid (port the contradiction check), because that check is not specific to declarative amendments.
- **Retain A:** if neither B nor C beats it on accuracy.

Results that fail a rule are reported as failures; condition C is not tuned on hidden results.
