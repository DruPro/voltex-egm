# Evidence policy (voltex3, Round 1): design and contracts

Status (2026-11-23): **G0 done; G1 groundwork in.** The evidence vector (3.1) is computed for every rule and shown by
`RULES EVIDENCE`; nothing reads it yet, and existing output is byte-identical (gate 221/221 against the previous
binary). Policies (3.2 to 3.4) are not built yet. Category: architectural change. The method is
`docs/EVALUATION.md`, extended by the round framework below; the full research framework, with its rationale, is the
shared document "EGM Research Round Framework: Policy-Thresholded Inference over Evidential Relationships".

## 1. The change in one line

How strict inference is becomes a **policy** applied to evidential relationships, not a difference in how knowledge
is stored. One representation (a rule with its evidence vector), one inference implementation, several policies.

## 2. Why: what the code does today

| Finding | Where | Consequence |
|---|---|---|
| A rule's evidence is collapsed into one `rel`; for relations with several values per subject `rel = min(1, rate / cov)` ignores known-answer agreement | `rescoreRules` (`src/voltex2.cpp`) | A small coverage estimate inflates reliability to 1: the dpkg rule labelled law at 0.15 agreement |
| Opposing evidence is only implicit: `pn - k` | `RuleH`, `mineRules` | In relations with several values per subject, `pn - k` is "unconfirmed", not "against" |
| Votes in one-value relations count paths, not tiers | `inferCore` | A tendency path can outvote a law path; `TENDENCYSTEPS 0` gave *more* correct tree-gate answers (1,332 vs 1,319, `studies/tendency`) |
| Two strict modes with different meanings | `TENDENCYSTEPS 0` (in inference), SDK `strict=True` (filter) | They can disagree; neither is a threshold over evidence |
| Three mechanisms let inference or votes change what learning sees | `QUARANTINE`, `VOTE`, `STALE` | Must be tagged and reported as evidence held out by a mechanism |

## 3. Contracts

### 3.1 `EvidenceVector` (induction, layer 3)

Computed for every candidate rule from stated facts only:

| Field | Meaning |
|---|---|
| `n` | chains the premises produce |
| `ePlus` | E+ = `k`: chains whose conclusion is stated |
| `eMinus` | E- = `pn - k` when the conclusion relation is one-value (0.95 test), else 0 |
| `eUnknown` | E? = `n - pn`: the subject has no known answer |
| `base`, `lift`, `z` | base rate of the conclusion, lift over it, agreement in standard deviations above chance |
| `agree` | E+ / (E+ + E-) where defined; for relations with several values: `k / pn` (reported, labelled as not opposing) |
| `cov` | the coverage estimate (strong inverse rules) |
| `halfA`, `halfB` | split-half agreement (the name-hash split of `replicate`) |
| `scope` | condition, if any (`CONDITIONS`) |

`rel` and `law` are **derived views** computed by the `legacy` policy exactly as today.

### 3.2 `Policy` (inference, layer 4)

A name and one threshold per component: `min_agree`, `min_known`, `min_z`, `min_lift`, `require_replicate`,
`max_tendency_steps`, `tier_votes`. Three named policies: `legacy` (today, byte for byte), `strict`, `tendency`.

### 3.3 Policy-closed inference

`inferCore(policy)`: only rules the policy admits propose facts; only facts derived under the policy feed later rounds;
with `tier_votes = 1`, in one-value relations law-tier paths decide before tendency paths are counted.

### 3.4 Derived-fact record (inference to presentation)

Adds `policy`, `weakest` (the weakest component value on the proof) and `round` to today's score, proof and tier. A
fact derived under `tendency` becomes `strict` only by being derived again under `strict`.

### 3.5 Evidence classes (evidence view, layer 5)

Every fact read by learning is `observed`, `observed-sourced` or `historical`. Facts held out are tagged
`held-out:quarantine`, `held-out:vote`, `held-out:stale`. Derived facts are never in the learning set.

### 3.6 Commands (presentation, layer 6)

`SET POLICY legacy|strict|tendency` (default `legacy`; experimental; saved in `.cfg`), `SET POLICY.<component> <v>`,
`RULES EVIDENCE` (the vector per rule), and the policy on every `ASK` line.

## 4. Capability claims (the capability track judges these, not resemblance)

- **Improve:** C5 calibration and selectivity (the risk-coverage curve); C3 precision at the strict operating point,
  on every structure and on real data.
- **Protect (no loss beyond seed spread on any structure):** C1 retention, C3 recall at the tendency operating point,
  C4 abstention, C9 consistency, C10 explanation fidelity, C12 cost (declared: at most 2x inference time when two
  policies run).

## 5. Layers crossed, and why

Induction produces the vector, inference consumes it, presentation shows it. A round that only built the vector
would leave a contract nothing uses, which can't be measured.

## 6. Invariants (permanent tests, gate G2)

1. Learning reads observed facts only; derived facts never count toward any E+, E- or E?.
2. Evidence held out by a mechanism is tagged, reported and reversible.
3. A label never goes up without re-derivation under the stricter policy.
4. One inference implementation; policies parametrize it.
5. `POLICY legacy` reproduces the previous release byte for byte (compatibility guarantee for an opt-in change, not
   evidence of progress).
6. Every cap prints `[LIMIT]`; every rate comes with its count.
7. No domain words in the engine.

## 7. Open owner decisions (to record before the pre-registration is hashed)

1. **Nesting. Decided 2026-11-23 (owner): yes.** Strict answers must be a subset of tendency answers. Strict admits
   tendencies that are validated or strong, judged on their evidence vector in the probability field, not only
   today's law label. Consequence: tier-aware votes (`tier_votes = 1`) in the strict and tendency policies, and C-H3
   is a requirement, not only a measurement.
2. **Which strict counts. Decided 2026-11-23 (owner): replace.** `POLICY strict` replaces `TENDENCYSTEPS 0` and the
   SDK's `strict=True`: no redundant features. Compatibility (a separate track): the old controls stay as aliases
   that map onto the policy until a major version, and the differences are listed (K3).
3. **Names.** Keep law and tendency as public labels, or move to the policy names?
4. **Representation.** Does `EvidenceVector` wrap `RuleH` or replace its scoring fields?
5. **Round 2 data independence.** Build categories on the discovery half only?
6. **Sealed worlds.** Who writes the second generator?
7. **External reference engines.** A non-EGM rule miner in the profile, or trivial baselines only?
8. **The interface.** Is the evaluation interface (`studies/capability/tools/interface.py`) frozen for later rounds?
