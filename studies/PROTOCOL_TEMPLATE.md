# <Study name>: pre-registration

Copy this file to `studies/<name>/PREREGISTRATION.md` and fill in every section before the first real run.
Then hash it:

```
echo "$(sha256sum PREREGISTRATION.md | cut -d' ' -f1)  PREREGISTRATION.md  $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> prereg_hash.txt
```

Any later change goes in `DEVIATIONS.md`, with the reason and what it affects. The method is described in
`docs/EVALUATION.md`. Don't delete sections; write "none" where one doesn't apply.

## 1. Capability or limitation

Which capability from the matrix in `docs/EVALUATION.md` (representation, induction, expressiveness, inference,
evidence, evolution, efficiency), and what exactly is being investigated. Quote the current boundary or the
measurement that motivates the study.

## 2. Owning layer

One of: storage, statistics, induction, inference, evidence view, presentation (`docs/THEORY.md`, section 3), or
outside the engine (SDK, extractor, MCP). If the change crosses layers, say why it can't live in one.

## 3. Hypothesis

Falsifiable, with a direction and a measurable outcome, for example: "`X 1` raises recall on worlds A and B without
lowering precision on any registered world by more than the baseline's seed-to-seed range."

## 4. Baseline (before any change)

- **Binary:** the engine commit and binary sha256.
- **Variance:** baseline numbers per world over at least 5 seeds, as mean, sd and range
  (`studies/eval/tools/scorecard.py`, or the study's own harness).
- **Tool commit:** the commit of every tool used. Stored hashes are comparable only within one tool version.

## 5. Design

- **Development worlds:** used while building; results from them are exploratory.
- **Confirmation worlds:** held out, run once after the design is frozen. Use at least two that are independent
  (different generators, or a generator plus real data).
- **Controls:** worlds where the right answer is "nothing" or "unchanged", such as a no-structure world, or a
  decoy relation.
- **Metrics:** each with its count. List the ones from `docs/EVALUATION.md`, section 5, that apply.
- **Expected failure modes:** what would make the change look good for the wrong reason.

## 6. Acceptance criteria

Write these after the baseline variance is known and before confirmation runs. Tie each threshold to the baseline:
- **Effect size:** the change beyond the baseline's seed range.
- **Hard limits:** for example, no new false discoveries on controls.

Don't pick round numbers without a reason.

## 7. Equivalence when off

A new behaviour is opt-in. With it off, the output must be byte-identical to the baseline on the gate
(`studies/scaling/tools/gate.py`, 221 cells) and the stress bench (`studies/stress/tools/bench.py`). Run both
binaries under the same tool version.

## 8. Replication

Which independent environment repeats the confirmation, with no tuning on it.

## 9. Reporting

Results go in `RESULTS.md`, with numbers recomputed from results files by a script. Report:
- failures next to wins;
- the cost: time, memory, extra evaluations;
- newly found limitations;
- what the result does not show.

Label everything designed after seeing data as exploratory.

## 10. Decision

Adopt (and as what: experimental or stable), keep as a study option, or reject, with the evidence for the choice.
