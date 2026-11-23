# Round 1 development log (G4): exploratory

Everything here was designed after seeing development data and is **exploratory**. Nothing in this file is evidence
of progress: that comes only from confirmation on sealed worlds and replication on real data, after the
pre-registration is hashed. The numbers are in the generated reports `dev/ITER1.md` to `dev/ITER3.md` (from
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

## Where the hypotheses stand (development only)

- **C-H3 (nesting):** holds by construction (stratified inference), and is measured as 0 violations.
- **C-H2 (strict >= 0.95 precision with recall >= `TENDENCYSTEPS 0`):** met except at low coverage, where replication
  costs recall. Open: how replication should behave when few answers are known.
- **C-H1 (better risk-coverage curve):** not met. The policies change the operating point, not the ranking; the
  ranking inside a stratum still uses the engine's score.
- **K-H0 (legacy byte-identical):** gate 221/221 after every engine change.

## Next

1. Low-coverage replication (C-H2): require replication only where enough known answers exist to test it, and report
   the rest as unvalidated rather than failed; or a minimum known count per half.
2. Ranking (C-H1): order answers by the weakest component of their proof's evidence (the `weakest` field of the
   derived-fact record, DESIGN 3.4), not by the legacy score.
3. Then freeze the built-in values, hash the pre-registration, and run confirmation.
