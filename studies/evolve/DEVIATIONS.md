# Deviations from PREREGISTRATION.md (recorded before the registered run)

1. A smoke run on seed 11 (a registered seed) was made while debugging the harness. It revealed (a) a harness bug: the
   D-x condition received A-style commands because the translator only recognised "D"; fixed; (b) scenario crowding:
   with all people-world scenarios in one session, ~12% of subjects carried two residences, which pushed `lives in` below
   the 0.9 one-value threshold shared by UPDATE, AMEND and both declarative builds (the same artifact found in the
   previous study). Each scenario now runs in its own session (realistic density). The combined session is kept as a
   separate, labelled stress test. No condition's logic was changed in response to seed-11 outcomes; further debugging uses seed 99.
