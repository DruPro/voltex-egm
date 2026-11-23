# Developing EGM (voltex3)

A guide for whoever implements the next change. It covers how the engine is put together since voltex3, where each
component lives, the rules every change has to keep, and step-by-step recipes for the kinds of change the research
rounds have made. Read `docs/THEORY.md` for why the engine works the way it does, and `docs/EVALUATION.md` for how
changes are judged. This file is about how to make one.

## 1. The pipeline

One engine binary (`src/voltex2.cpp`, a single translation unit) and a Python SDK (`egm/`) that drives it over a
line protocol. Evidence flows through five layers, and every change belongs to exactly one of them:

```
records ──► statistics ──► induction ──► evidence vector ──► policy evaluation ──► inference ──► presentation
            (grammar,      (rules and    (E+, E-, E?,       (admits(), per        (stratified   (ASK, tiers,
             categories,    their test,    agreement, z,      stratum; validation   fixpoint)     proofs,
             relations)     coverage)      coverage source,   as an evaluation)                   [POLICY] line)
                                           stability)
```

| Layer | Owns | Entry points in `src/voltex2.cpp` (struct `Vault`) |
|---|---|---|
| statistics | Sequitur grammar, Witten–Bell counts, word categories, two-slot relations | `buildClasses`, `buildRelations` |
| induction | candidate rules (inverse, chain, path, tree, conditional), the shipped acceptance test, coverage estimate, conditions | `mineRules` → `minePaths` (CHAIN 3+) → `rescoreRules` (`estimateCoverage`) → `specialize` (CONDITIONS) → `mineTrees` (TREES) → `replicate` (REPLICATE) → `computeEvidence`; `passes` re-applies the shipped test |
| evidence vector | per-rule numbers that policies read; nothing in induction reads them back | `computeEvidence`, `covSourceDesc`, `covSourceAgree`, `stability`, `internalReplication` |
| policy evaluation | which rules each stratum admits | `admits`, `evaluatePolicy`; `Stratum`, `PolicyCfg pol` |
| inference | the fixpoint, depth, tiers, weakest step per fact | `inferCore`, `infer`, `policyInfer` |
| presentation | answers, labels, proofs, `RULES EVIDENCE`, `POLICY SHOW`, `SNAPSHOT` | the command loop at the end of the file |

`ensureModel` runs the first three layers when the evidence has changed (or the cheap `REFRESH` path); `ensureInferred`
runs inference. Policy evaluation is lazy: `policyEvaluated` resets on every model rebuild and on every `POLICY`
command, and `evaluatePolicy` clears the evaluation caches (`validation`, the prediction capture, stability).

The SDK mirrors the layers: `egm/engine.py` (process, commands, `evidence()`, `apply_policy`, `compare_policies`),
`egm/policy.py` (the policy schema, validation, registry, built-ins), `egm/parse.py` (output parsing), `egm/model.py`
(`Fact`, `PolicyComparison`), `egm/cli.py` (the `egm` command), `egm/mcp_server.py`.

## 2. Rules every change keeps

1. **Legacy is byte-identical.** A new behaviour is a setting that is off by default, or a policy field whose default
   restricts nothing. After every engine change:
   `GATE_TAG=<tag> python3 studies/scaling/tools/gate.py <pre-voltex3 binary> build/voltex2` must print
   `221/221 identical`. The pre-voltex3 binary is `main`'s engine, where voltex3 branched:
   `git show $(git merge-base voltex3 origin/main):src/voltex2.cpp > /tmp/base.cpp && g++ -O2 -std=c++17 -o
   /tmp/voltex2-base /tmp/base.cpp` (checked: a binary built this way is gate-identical to the one Rounds 1 and 2
   used). `studies/v21_baseline/` is the older v2.1 engine, not this baseline. Then `make test`.
2. **Fix a fault in the layer that owns it.** Round 2's dpkg flood came from the coverage estimate (induction); a
   policy field (W1a) could not reach it because the bad rules were accepted before any policy ran. Measure where the
   fault is before choosing the layer (`studies/round2/DEVELOPMENT.md`, W1).
3. **Validation is an evaluation, not a property.** Anything that judges a rule (replication, stability, a future
   independent-source check) is recomputed per evidence snapshot, recorded with its method, and never stored on the
   rule as a fact about it.
4. **Evidence never contains derived facts.** Every count in the evidence vector comes from stated facts. Contract
   X-H1 (Round 1) checks it.
5. **Every policy field is enforced by the engine.** A field the engine can't enforce isn't offered. Unknown fields and
   out-of-range values are errors on both sides (`egm/policy.py` `validate()` and the engine's `POLICY APPLY` parser).
6. **Results name what produced them.** Answers under a policy print `[POLICY] name@version`; studies record the
   binary's sha256 and the tool commit.

## 3. Recipes

### Add an evidence component

Example: Round 2's `stability` and `cov_source`.

1. Compute it in the evidence layer. If it judges the rule, make it a lazy, cached evaluation (pattern: `stability()`,
   `internalReplication()`), clear the cache in `evaluatePolicy`, and reuse `captured()` if you need each rule's
   predictions (one capture serves every evaluation).
2. Print it in `RULES EVIDENCE` as a new `key=value` field (append; the SDK parses fields by name). Use `undef` for
   "no value".
3. Parse it in `egm/engine.py` `evidence()` with `kv.get(...)`, so older binaries still parse.
4. Document it in `docs/EVIDENCE.md`.

Pitfall (Round 2, W1): don't keep an index into `ruleList` across a rebuild step; the list is reordered after
estimation. Store the value you need at the time you compute it.

### Add a policy field

Example: `minStability`, `minCoverageSourceAgreement`.

1. Engine: a member in `struct Stratum` with a default that restricts nothing; a check in `admits()`; a branch in the
   `POLICY APPLY` field parser with an explicit range error; the field in the `STRATUM` line of `POLICY SHOW`.
2. SDK: one entry in `THRESHOLDS` (or `VALIDATION`/`INFERENCE`) in `egm/policy.py`: `"name": (kind, default,
   engine_key)`. Kinds: `count`, `share`, `number`, `nonneg`, `bool`, `method`, `split`, `insufficient`, `shapes`. The
   CLI and the registry pick it up from the schema; nothing else changes.
3. Tests: `tests/test_policy.py` (validation error, round trip through export/import, the engine enforces it).
4. Document it in the contract table in `docs/POLICIES.md`.

Built-in policies are frozen: never add a field to a built-in's configuration; offer a cloned example instead.

### Add an opt-in induction setting

Example: `COVSOURCE`, `CONDHOLDOUT`.

1. A member `int F_X = 0;` near the related settings, and one `VTX_SETTING("NAME", "induction", true, true, "help
   (studies/<study>)", F_X, int)` line in `settings()` (experimental = true; saved = true so `SAVE`/`LOAD` keep it).
2. Branch on it so the shipped path is textually untouched when off (W3 adds its search as a separate branch and
   `continue`s; W1b only changes what `covFor` returns when on).
3. If it changes induction, check whether the `REFRESH` fast path in `ensureModel` must be disabled for it.
4. Gate, `make test`, and a row in `docs/SETTINGS.md`.

### Add a rule shape or a condition kind

Add the miner in the induction layer; give it a `type` letter and a `shapeOf` bit so policies can include or exclude
it (`inference.shapes`); make `passes` (or its own test) the acceptance test, `ruleText` its rendering, and
`remapRules`/`cacheRules` its persistence. Then the capability suite: a development world in
`studies/capability/tools/cworlds.py` and, for confirmation, a structure in the next sealed generator (written by a
separate agent from a spec, section 5).

### Add a capability metric

`studies/capability/tools/metrics.py` `measure()` returns a dict; add keys, never change the meaning of an existing
one. The interface (`interface.py`: `Answer`, `Run`, adapters with `run()` and optionally `ask()`) is frozen and only
extended with optional fields. Round 2 example: undeterminable keys with three elements.

## 4. Testing and checking

| What | Command | When |
|---|---|---|
| Unit tests and kit checks | `make test` | every change |
| Legacy byte-identity | `python3 studies/scaling/tools/gate.py /tmp/voltex2-base build/voltex2` | every engine change |
| Stress bench | `python3 studies/stress/tools/bench.py run build/voltex2 <out.jsonl>` (needs `bench.py catalog` and `/usr/bin/time`) | before a release |
| Capability profile | `python3 studies/capability/tools/profile.py --md <file>` (never overwrite `BASELINE.md` from a development run) | per iteration |
| Sanitizers | `make sanitize` | after memory-touching changes |

Debugging an induction decision: `RULES EVIDENCE ALL` shows every candidate with its vector. For a decision inside a
search (why a condition was rejected), a temporary `if (getenv("VTX_DEBUG")) fprintf(stderr, ...)` is fine; the SDK
merges stderr into stdout, so drive the binary directly (`INGESTFILE`, then the command) and never commit the print.

## 5. Running a research round

The framework is in `docs/EVALUATION.md` and `docs/RESEARCH_ROUNDS.md` (how to use the tooling). The short version,
with the files Round 2 produced as the template (`studies/round2/`):

1. `DESIGN.md`: the open findings, a diagnosis on development data, workstreams with their owning layer, contracts,
   capability claims, and the owner decisions (ask before building anything that depends on them).
2. Development: `DEVELOPMENT.md`, one section per iteration, with the numbers, the files that hold them, and what
   failed. Development data only.
3. A sealed generator for confirmation, written by a separate agent from a spec (`studies/sealed2/SPEC.md`) and the
   output format alone; it does not read the engine.
4. Harness validation without running the engine on confirmation data (planted engines, an oracle, a dry run on
   development data).
5. `PREREGISTRATION.md` hashed into `prereg_hash.txt` before the run; criteria applied mechanically by a report script.
6. Confirmation exactly as written; `RESULTS.md` (generated), `DEVIATIONS.md`, `CONFIRMATION.md` (reading and the
   decisions the pre-registration fixed in advance).

Things that went wrong before and are now rules: module names in tool folders must be unique across `sys.path`
(`worlds.py` and `report.py` shadowed others); generated reports take an output path and never overwrite the G3
baseline; `results/` folders are committed; don't run anything on confirmation data before the hash, not even for
timing (Round 1 D1).

## 6. Open work (after Round 2)

See `studies/round2/CONFIRMATION.md` for what the confirmation decided. Known open items:

- **Coverage estimation beyond inverse rules.** W1b refuses an estimate the evidence contradicts; it doesn't produce a
  better one. Relations without a trustworthy inverse have no estimate at all.
- **Thin conditions.** A condition resting on a handful of subjects can't be confirmed out of sample (W3); the shipped
  search accepts some anyway. A minimum-subjects requirement per condition is the obvious next candidate.
- **Stability of the estimator.** The subject bootstrap holds coverage fixed by design; a bootstrap that re-estimates
  coverage per resample would catch estimator instability directly (at R× the cost).
- **Investigation V** (independent-source validation and decay) is designed (`studies/evidence_policy/DESIGN.md`) and
  not built; `validation.method` is where it plugs in.
- **Help text:** `COVSOURCE`'s `CONFIG` text says "exceeds (z > 3)"; the test is against c / RATE_REL (fixed after the
  Round 2 confirmation, `studies/round2/DEVIATIONS.md`).
