# Evidence policy (voltex3, Round 1): design and contracts

Status (2026-11-23): **G0 done; G1 and G2 in; G4 development under way** (`DEVELOPMENT.md`). The evidence vector,
configurable policies (engine `POLICY APPLY`, SDK registry, CLI `egm policy`) and stratified inference are built;
`legacy` stays byte-identical (gate 221/221 against the pre-voltex3 binary). User documentation: `docs/POLICIES.md`. Category: architectural change. The method is
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

### 3.2 Policies: configurable inference contracts (inference, layer 4)

Owner requirement (2026-11-23): policies are first-class, configurable and versioned, in the SDK and the CLI; the
built-ins are reference profiles, not a closed set.

- **Engine:** executes a fully specified configuration and stores no names (`POLICY APPLY <name> <version>
  core.<field>=<v> ... [extension.<field>=<v> ...]`, `POLICY SHOW`, `POLICY LEGACY`). Every field is validated; on
  any error the active policy is unchanged. A policy is not saved with the knowledge base.
- **SDK (`egm/policy.py`):** the configuration contract (every field with semantics, range and default), validation
  with explicit errors, a versioned registry (create, update = new version, get, list, clone, export, import), the
  built-ins, and `Engine.apply_policy`, `infer_all/ask(policy=)`, `compare_policies`, `snapshot`.
- **CLI (`egm policy ...`, `egm infer --policy`, `egm ask --policy`):** a front end to the same module.
- **Built-in semantics (owner, 2026-11-23):** legacy preserves existing behaviour exactly; tendency admits rules by
  their configured evidence thresholds, without replication; strict requires minimum evidence, acceptable agreement
  and split-half replication.

### 3.3 Validation is an evaluation, not a property (owner, 2026-11-23)

`validated = evaluate(rule, method, evidence snapshot)`: recomputed per build, never stored on the rule, and reported
with its method (`internal_replication/hash` or `internal_replication/blocked`), so internal replication can't be read
as independent-source confirmation. Investigation V adds `independent_sources` as another method without changing the
representation. `blocked` splits subjects by first appearance (ingestion order), for time-ordered or correlated data,
where a hash split can make one regime look replicated (owner, 2026-11-23).

### 3.4 Stratified, policy-closed inference and the derived-fact record

A policy has a core stratum and an optional extension. The core's rules run to their own fixpoint; the extension's
rules (with the core's) then extend it without overriding anything the core decided. So a policy's answers contain its
core's answers (the owner's nesting decision holds by construction), extension-derived facts are labelled `extension`,
never `core`, and each stratum has its own `maxDepth`. Results name the policy (`[POLICY] name@version`,
`Fact.policy`); `SNAPSHOT` identifies the evidence state. Every derived fact under a policy carries `weakest`, the lowest rule reliability on its best proof (iteration 4).

### 3.5 Evidence classes (evidence view, layer 5)

Every fact read by learning is `observed`, `observed-sourced` or `historical`. Facts held out are tagged
`held-out:quarantine`, `held-out:vote`, `held-out:stale`. Derived facts are never in the learning set.

### 3.6 Commands (presentation, layer 6)

`POLICY APPLY|SHOW|LEGACY`, `SNAPSHOT`, `RULES EVIDENCE [ALL]` (vector, validation result with its method, admitting
stratum), and a `[POLICY] name@version` line before `ASK` and `INFER` output under a policy.

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
3. **Names. Decided 2026-11-23 (owner):** `law`/`tendency` under legacy, `core`/`extension` under a policy, so a
   label never claims more than its stratum.
4. **Representation. Decided 2026-11-23 (owner):** the evidence vector wraps `RuleH` (as built).
5. **Round 2 data independence. Decided 2026-11-23 (owner):** yes, build categories on the discovery half only,
   and measure the cost.
6. **Sealed worlds. Decided 2026-11-23 (owner):** a separate agent writes the second generator from the structure
   list alone, without access to the development worlds or the engine source (`studies/sealed/`).
7. **External reference engines. Decided 2026-11-23 (owner):** add one AMIE-style rule miner as an external
   baseline (`studies/capability/tools/baselines.py`, B3).
8. **The interface. Decided 2026-11-23 (owner):** frozen as of this commit; later rounds extend it only by adding
   optional fields, never by changing existing ones.
9. **Validation. Decided 2026-11-23 (owner):** an evaluation result with its method recorded (3.3); Round 1 uses
   internal split-half replication, named as such; built-in semantics as in 3.2; blocked splits for correlated data.
10. **Custom policies. Decided 2026-11-23 (owner):** first-class in the SDK and the CLI (3.2, `docs/POLICIES.md`).
