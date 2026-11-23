# Round 1 confirmation: analysis and decision

The verdicts and every number are in `RESULTS.md`, generated from `confirm/results/` by `confirm/confirm_report.py`,
which was written and committed (f021736) before the run. This file interprets them. The confirmation ran once:
14 sealed structures (`studies/sealed`, written independently) x seeds 1000-1004, and four real-data sets x five
splits (`confirm/REALDATA.md`). Deviations: `DEVIATIONS.md` D1-D3, all recorded before the run. No setting, threshold,
policy value or harness line was changed after any confirmation result was seen.

## Does Round 1's frozen architecture generalize beyond its development worlds?

**Partly. Its structural guarantees generalized; its precision claim did not; its ranking gain was not shown.**

| Hypothesis | Verdict | What it means |
|---|---|---|
| C-H3 nesting | **pass** | strict's answers are inside tendency's on every world, every seed (0 violations; `TENDENCYSTEPS 0` had up to 18 per seed in development) |
| C-H4 no invention, quiet control | **pass** | 0 facts about unseen entities under either policy; 0 derived on the no-structure control |
| C-H5 proofs valid and faithful | **pass** | 1,042,818 proofs checked, 0 invalid; 2,000 counterfactual tests, 0 failures (1,975 facts vanished when their premises were removed, 25 had a genuine second proof) |
| K-H0 compatibility | **pass** | legacy byte-identical: gate 221/221, full stress bench 313/313 on this machine |
| X-H1 contracts | **pass** | no label upgrades; the evidence snapshot never changes under any policy |
| C-H2 strict precision | **FAIL** | precision >= 0.95 on 10 of 13 counted worlds; fails on `conditional` (0.047), `conditional_decoy` (0.048) and `dpkg` (0.006). The recall clause passed everywhere |
| C-H1 better ranking | **pass as written, not demonstrated** | 9 of 15 worlds count as improved, but all 9 by equality (AURC 0 against 0, sd 0): the weakness recorded in DEVIATIONS D2 before the run. 0 worlds improved strictly; on real data tendency's AURC was slightly higher than the default's (unicode 0.023 vs 0.018, py_dist 0.712 vs 0.701), inside the tolerance. The development gain from weakest-evidence ranking did not replicate |

## The C-H2 failure, attributed to its layer

The failure is inherited, not introduced: on all three worlds the strict policy is exactly as precise as today's
`TENDENCYSTEPS 0`, and on the conditional worlds exactly as precise as every profile, including the external AMIE
miner (0.047 everywhere, the same 790 answers). So:

- **Conditional worlds: the data's missing-is-not-false limit, which a policy cannot see.** The true rule holds only
  for a qualifying group; outside it the conclusion is never stated, so those subjects look unknown rather than wrong,
  agreement where answers are known is about 1.0, and replication passes. No admission threshold can tell this rule
  from a law: the evidence that it over-generalizes is absent, not weak. This is the Farmers problem, and it is
  solved in the induction layer, by conditions: the shared-conditions study recovered exactly these structures from the
  same independent generator (seeds 2000-2004) with conditional precision 1.000. With `CONDITIONS` off by default, the
  strict policy's precision guarantee does not hold for conditional structure. That is a scope limit of policies,
  consistent with the design (policy admits; it doesn't change what a rule says).
- **dpkg: flooding rules admitted under every strict option.** The data are bimodal across splits: in splits 1000
  and 1003 the engine accepts rules that derive 58,000 to 119,000 facts, in the other three about 330 (and strict
  none). Strict and `TENDENCYSTEPS 0` admit the same flooding rules, at 0.006 precision against the direct facts.
  Against the transitive Depends closure, about 20% of the flood is a true indirect dependency (11,863 of 57,626 in
  split 1000), so the flood is mostly wrong under either reading. Where the hidden 20% falls decides whether the rules
  pass, which is an induction-layer instability (acceptance on thin, split-dependent evidence), not an admission
  problem the frozen thresholds were designed to catch.

## What else the run showed

- **Real code:** strict matched `TENDENCYSTEPS 0` at precision 1.000 on both Python codebases, where the default is
  at 0.006 (stdlib) and 0.087 (dist-packages): the policy reproduces the known best operating point, closed and
  nested, through the configurable mechanism.
- **Tendency's extension depth helps on long chains:** the depth world's recall 0.997 against 0.948 for the default
  (the extension's own depth budget, declared in development).
- **The sealed generator is easy for most structures:** on 12 of 14, every EGM profile's precision is 1.000 or it
  derives nothing; only the two conditional worlds separate the profiles (branching and path3 derive nothing because
  they need `TREES` and `CHAIN`, off by default). That limits what C-H1 could show; a harder generator
  (mixed-reliability rules, partial coverage) is needed to test ranking.
- **D-H1 (diagnostic):** across 216 rules with at least 5 new facts under tendency, rule precision correlates weakly
  with known-answer agreement (Spearman 0.309) and with `rel` (0.354). Neither is a good predictor of a rule's
  precision on unseen data; the development hint that agreement would beat `rel` did not hold.

## Decision (pre-registered options, section 10)

By the decision rules: the policies are better on some capabilities (C9 consistency: ordered, nested policies where
`TENDENCYSTEPS 0` was not; C10: closed, valid, faithful proofs, where the SDK's old strict filter was not), equal on
precision and recall everywhere the old options worked, and worse nowhere beyond the tolerance. The pre-registered
precision claim (C-H2) failed, and the ranking claim (C-H1) was not shown.

**Recommended: adopt `POLICY` as an experimental feature with `legacy` as the default, and do not present strict as
a precision guarantee.** State in `docs/POLICIES.md` that strict is precise when the evidence can expose a bad rule,
and is not when a rule over-generalizes into unstated territory (use conditions) or floods on thin evidence. Changing
any default stays a separate decision. The owner decides.

## What Round 2 should take from this

1. Over-generalization into unstated territory is an induction problem: conditions (with held-out proposal, from the
   shared-conditions study) are the lever, not admission thresholds.
2. Split-dependent acceptance of flooding rules (dpkg) needs its own study: acceptance stability across resamples as an
   evidence component, so a rule that passes on one split and fails on another is reported as unstable.
3. C-H1 needs worlds that can discriminate rankings, and a criterion without the equality loophole.
