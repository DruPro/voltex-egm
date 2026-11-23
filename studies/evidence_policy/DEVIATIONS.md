# Round 1 deviations

Every departure from `PREREGISTRATION.md` (hashed 2026-11-23T18:52:01Z), recorded when it happened, before the
confirmation run unless stated otherwise.

## D1. Real-data results seen during a timing check (before confirmation)

While timing the harness, `policy-tendency` was run once on split 1000 of each real-data set (the confirmation splits)
to estimate run time. Its results were therefore seen before the confirmation run: precision 0.011 (dpkg), 0.963
(unicode), 0.005 (py_stdlib), 0.077 (py_dist). Nothing was changed afterwards: built-in values, acceptance criteria
and harness are as frozen. The confirmation run reruns every profile on every split. Recorded so the reader can weigh
it; the sealed synthetic worlds were not run.

## D2. Interpretations fixed before the confirmation run

- "Real data" (C-H2): the four sets in `confirm/REALDATA.md` (py_stdlib, py_dist, unicode, dpkg), five held-out
  splits each (seeds 1000-1004). The pre-registration named "dpkg, Unicode, strengths"; strengths' two codebases are
  py_stdlib and py_dist, rebuilt on this machine.
- C-H5's counterfactual test ("a 100-fact sample per world") runs on the sealed worlds: 20 facts per seed x 5 seeds
  per structure, under policy-strict and policy-tendency. On real data, C-H5 is checked by proof validity only (a
  counterfactual rerun of the larger sets is too slow for 100 facts each). Proof validity runs everywhere.
- Real data gets `MAXWORDS` = distinct words + 1,000 for every profile (docs/CHOOSING_SETTINGS.md step 1, a capacity
  setting reported by `[LIMIT]`), fixed before any run and identical across profiles.
- Sealed structures where a profile derives fewer than 20 facts per seed are reported but don't count toward
  precision criteria (as pre-registered). "Worlds with derived facts" for C-H1 means egm-default derives >= 1 fact.
- The SDK's `strict=True` is not used by the confirmation; policy-strict is the engine-level policy (`POLICY APPLY`),
  as the owner required. The SDK correction (commit 7538d2e) changed no engine behaviour.
- "World" in C-H1, C-H3, C-H4 and C-H5's proof validity: every sealed structure and every real-data set. C-H5's
  counterfactual: sealed structures only (above). The control world for C-H4 is the sealed `control` structure.
- "Under every policy" (C-H4, C-H5): policy-strict and policy-tendency; egm-default and egm-ts0 are reported.
- The "fewer than 20 derived facts per seed" rule for precision criteria applies to real data too.
- A weakness noticed in the frozen C-H1 criterion, applied as written: where egm-default's AURC has sd 0 across
  seeds, "AURC(tendency) <= AURC(default) - 2 sd" is met by equality, so an unchanged AURC counts as an improvement.
  The report gives the number of worlds that improve strictly beside the pre-registered count.

## D3. Stress-bench equivalence on this machine (K-H0)

`studies/stress/tools/bench.py` times every cell with `/usr/bin/time`, which this machine lacks; unmodified, every
cell would fail identically for both binaries and "match" vacuously. A minimal stand-in (`/usr/bin/time` implementing
only `-f "%e %M" -o FILE`, elapsed seconds and the child's peak RSS) was installed; the bench itself is unchanged.
Equivalence is judged on output hashes, which don't depend on timing. The catalog was rebuilt on this machine
(`bench.py catalog`): `code_js` is empty here (no JavaScript sources installed), and the datasets differ from the
stress study's machine; both binaries run on the same catalog. Both bench runs ran concurrently with each other.
