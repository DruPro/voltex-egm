# studies/eval: baseline and validation for the evaluation framework

The framework is in `docs/EVALUATION.md`. This folder holds what makes it measurable:

- **`tools/scorecard.py`:** a capability baseline. It runs the existing generators (`studies/noise`,
  `tests/worlds.py`) with the existing scorer (`studies/noise/tools/lib.py`), and adds tier calibration, variance
  over seeds and a no-structure control. It writes `baseline/scorecard.json`.
- **`tools/report.py`:** writes `BASELINE.md` from `baseline/` and `validation/`.
- **`validation/`:** re-runs of the repository's existing tools on this commit:
  - the gate against itself, against a one-setting change, and against a rebuild of `ac54dd9`;
  - the stress bench against its recorded C1 run.

Reproduce:

```
python3 studies/eval/tools/scorecard.py                                   # baseline/scorecard.json
python3 studies/eval/tools/scorecard.py --out studies/eval/baseline/scorecard_repeat.json   # determinism check
GATE_TAG=eval_self python3 studies/scaling/tools/gate.py build/voltex2 build/voltex2
python3 studies/stress/tools/bench.py run build/voltex2 studies/eval/validation/bench_main.jsonl
python3 studies/eval/tools/report.py
```

`obs/` (generated worlds) is git-ignored. The stress bench needs its datasets built first
(`studies/stress/tools/bench.py catalog`), and they depend on what is installed on the machine.
