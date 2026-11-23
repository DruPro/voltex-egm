# Round 1 development log (G4): exploratory

Everything here was designed after seeing development data and is **exploratory**. Nothing in this file is evidence
of progress: that comes only from confirmation on sealed worlds and replication on real data, after the
pre-registration is hashed. The numbers are in the generated reports `dev/ITER1.md` to `dev/ITER4.md` (from
`dev/iter*.json`, by `studies/capability/tools/profile.py --report`); the summaries below quote them.

Iterations 1 and 2 ran on intermediate engine builds (binary sha256 in each JSON's `meta`) whose policy controls were
engine settings (`SET POLICY`). Those settings were replaced by `POLICY APPLY` and the SDK registry before iteration 3,
so iterations 1 and 2 can't be rerun from this commit; they are kept as the record of what was tried.

## Iteration 1: agreement as the strict criterion

Strict = accepted, known cases >= 5, known-answer agreement (E+ / known) >= 0.8, internal replication (hash split).
Tendency = the strict stratum, then every accepted rule.

- **Failed.** Strict precision fell below `TENDENCYSTEPS 0` in every `hidden` world (0.785 to 0.900 against 0.992 to
  0.997) with far lower recall, and admitted harvest's over-general rule (precision 0.029).
- **Why (refinement R1):** with several values per subject a missing conclusion is unknown, not opposing, so
  E+ / known misjudges reliability both ways: it drops real rules (agreement 0.69 to 0.80 on many-value conclusions)
  and admits harvest's rule (agreement about 0.9, because only farmers and miners have harvest facts at all).
- **Confound found:** the tendency stratum had its own full depth budget, so remainders recall rose (0.853 to 0.924)
  from extra depth, not from better evidence.

## Iteration 2: reliability by relation type; shared depth budget

Strict reliability = agreement for one-value conclusions, the coverage-corrected rate (`rel`) otherwise, >= 0.95, plus
an agreement floor of 0.5 (against the dpkg case: `rel` 1.0 at 0.15 agreement). Depth: one budget shared by both strata.

- Strict now matched `TENDENCYSTEPS 0`: precision 0.992 to 1.000 at similar recall, except `hidden` at 30% coverage
  (precision 0.971, recall 0.044 against 0.355: replication needs known answers, and few are known there).
- Harvest: strict derives nothing, as `TENDENCYSTEPS 0` does.
- **The shared budget starved tendency** at 30% coverage (recall 0.116 against 0.393): the strict stratum used every
  round. Rejected.

## Iteration 3 (committed): configurable policies; depth per stratum

Policies became configurable inference contracts (owner requirement, `docs/POLICIES.md`): the engine executes any
valid configuration (`POLICY APPLY`), the SDK registry holds built-ins and custom versions, and the depth budget is an
explicit per-stratum field (`inference.maxDepth`, 4 for both built-in strata). Built-in `strict` keeps iteration 2's
criteria; `tendency` extends it with every accepted rule.

| Finding (5 seeds) | Value | Against |
|---|---|---|
| Nesting: strict answers outside tendency | 0 in every world and seed | `TENDENCYSTEPS 0` outside default: up to 18 per seed |
| Strict precision | 0.992 to 1.000, except 0.971 at `hidden` 30% | `TENDENCYSTEPS 0`: 0.992 to 1.000 |
| Strict recall at `hidden` 30% | 0.044 | `TENDENCYSTEPS 0`: 0.355 |
| Tendency vs default | precision 0.989 vs 0.986 (noise 15%), 0.919 vs 0.915 (`hidden` 70%); recall equal or higher | |
| Tendency on remainders | recall 0.924 vs 0.853: the extension's own depth budget (declared, a policy choice) | |
| AURC (C5) | no improvement over legacy yet; tendency slightly worse at `hidden` 30% (0.031 vs 0.019) | C-H1 not met |
| Harvest | tendency still admits the over-general rule (needs `CONDITIONS`); strict derives nothing | |

## Iteration 4 (committed): agreement relative to coverage; insufficient vs failed; weakest-evidence ranking

Analysis of iteration 3 at 30% coverage: replication was not the cause (almost every rule passed it). Strict's fixed
agreement floor (0.5) was: for conclusions with several values per subject, a true rule's agreement is about the
conclusion relation's completeness (agreement / coverage estimate was 0.9 to 2.2 for the rules there, at every coverage
level), so a fixed floor reads incomplete data as an unreliable rule.

- Strict: the fixed floor is replaced by `minAgreementToCoverage` 0.8 (several values per subject, where a coverage
  estimate exists).
- Replication: a rule with fewer than `minPerHalf` (5) known answers in a half is `insufficient`, not failed; the policy
  chooses (`onInsufficient`; strict rejects).
- Ranking: every derived fact carries `weakest`, the lowest rule reliability on its best proof; the harness ranks
  policy answers by it.

| Finding (5 seeds) | Iteration 4 | Iteration 3 | Reference |
|---|---|---|---|
| Strict at `hidden` 30%: precision / recall | 0.997 / 0.351 | 0.971 / 0.044 | `TENDENCYSTEPS 0`: 0.996 / 0.355 |
| Strict at `hidden` 50%, 70%: recall | 0.463, 0.524 | 0.443, 0.524 | 0.467, 0.525 |
| AURC, tendency (`hidden` 30 / 50 / 70%, noise 15%) | 0.002 / 0.003 / 0.007 / 0.001 | 0.031 / 0.010 / 0.025 / 0.010 | default: 0.019 / 0.009 / 0.024 / 0.013 |
| AURC, strict (same worlds) | 0.001 / 0.001 / 0.000 / 0.000 | 0.057 / 0.009 / 0.020 / 0.000 | `TENDENCYSTEPS 0`: 0.017 / 0.009 / 0.020 / 0.000 |
| Harvest | unchanged: one over-general rule can't be ranked apart from itself; strict derives nothing | | |
| Nesting | 0 violations | 0 | |

Untested here: the stress study's dpkg rule (law at 0.15 agreement) does not occur in this machine's package data
(8,861 facts against 14,296 in the stress study), so whether strict excludes it is a confirmation item, not a claim.

## Where the hypotheses stand (development only)

- **C-H3 (nesting):** holds by construction (stratified inference), and is measured as 0 violations.
- **C-H2 (strict >= 0.95 precision with recall >= `TENDENCYSTEPS 0`):** in development, precision 0.992 to 1.000
  everywhere and recall within 0.004 of `TENDENCYSTEPS 0` (inside the seed spread); whether that counts as "at least"
  is decided by the acceptance thresholds fixed before confirmation.
- **C-H1 (better risk-coverage curve):** in development, lower AURC than legacy on every structure with derived facts,
  and equal on harvest.
- **K-H0 (legacy byte-identical):** gate 221/221 after every engine change.

## Next

1. Freeze the built-in values (iteration 4) and the acceptance thresholds (from the baseline seed spread).
2. Record the six remaining owner decisions and hash the pre-registration.
3. Build the sealed confirmation worlds (a separately written generator) and the real-data replication (`strengths`,
   Unicode, a dpkg dataset with the stress study's rule), then run confirmation once.
