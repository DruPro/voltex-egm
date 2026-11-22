# Deviations

## 1. Exploratory configuration added after the registered runs

After seeing `mixed_s1` (47 wrong, all tendency-tier, from the rule "an AND gate's output is zero", agreement 0.80),
one configuration was added: `trees_depth0_lawonly` (`TREES 1`, `DEPTH 0`, `TENDENCYSTEPS 0`). It runs on every world
and seed. It is not part of the registered verdicts (`tools/run.py verdicts` leaves it out), and RESULTS.md labels it
exploratory. The setting is the one `docs/CHOOSING_SETTINGS.md` already recommended for answers you act on.
