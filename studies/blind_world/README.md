# Voltex Blind World Discovery — reproducible package

Frozen system: frozen/voltex2.cpp (sha256 in frozen/FREEZE.txt). Never modified during the experiment.

Layout
  frozen/          frozen Voltex source + binary + freeze record (checksums, compiler, default thresholds)
  hidden/          world.py (generator + ground truth), evaluate.py (scorer), truth_*.json, info_*.json
                   Voltex never reads anything here.
  obs/             the ONLY inputs Voltex received (one fact per line)
  logs/            complete Voltex session logs (every command, output and latency)
  results/         main_runs.json, aggregate.txt, update_test.json, scaling.json
  lib.py           runners: Voltex (via its normal commands), graph-traversal baseline, true-rule oracle
  run_experiment.py  5 seeds x 30/50/70% coverage x 4 systems
  run_update.py      capability E (facts change after ingestion)
  run_scaling.py     500 -> 4,000 individuals
  aggregate.py       mean +- s.d. tables and the rule catalogue

Reproduce
  g++ -std=c++17 -O2 frozen/voltex2.cpp -o frozen/voltex2
  python3 run_experiment.py && python3 aggregate.py && python3 run_update.py && python3 run_scaling.py
Requires Linux with stdbuf (coreutils) and Python 3.
Only configuration change: SET SUPPORT 1000000000 for the rules-disabled baseline.
