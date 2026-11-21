# Pre-registration: CLUSTERSTREAM as the default

Written 2026-11-21, before the checks below (hash in `promotion_hash.txt`). The owner listed "make CLUSTERSTREAM the
default" as step 1 of the core plan.

**Change.** In `src/voltex2.cpp`, `F_CSTREAM` starts at 1, and the setting moves from experimental to stable
(`statistics` layer, still saved with the knowledge base). `SET CLUSTERSTREAM 0` keeps the listed-pairs path. Nothing
else changes.

**Evidence already in hand** (`RESULTS.md`): E1 221/221, E2 10/10, the core gates off and on 221/221, the sanitizer
gate 221/221, and a knowledge base saved with the setting opened by the previous engine with the same answers.

| ID | Claim | Pass if |
|---|---|---|
| P1 | The new default gives the previous build's output | Gate: new build with defaults vs previous build (`ac54dd9` binary, sha256 443b7a46...), 221/221 identical, apart from the lines a changed default must change (listed below) |
| P2 | The old path is still there | Gate: new build with `CLUSTERSTREAM=0` vs the previous build, 221/221 identical |
| P3 | Same answers at scale | company scale 32 and 64 seed 0, gates 1600 seed 0: identical `RELATIONS` + `INFER ALL` + `CONFLICTS` output, new default vs previous build |
| P4 | Memory | company scale 64 seed 0 with defaults: peak RSS (`/usr/bin/time`) <= 300 MB, against 8,350 MB before |
| P5 | Suites | `make test` and `make sanitize` pass |

**Lines a changed default must change:**
- `CONFIG` prints the new default.
- An explicit `SET CLUSTERSTREAM 0`, now non-default, is saved in `kb.vtx.cfg` and named in `[CONFIG]` restore
  lines.

The gate compares no `CONFIG` output. P2's `[CONFIG]` restore notice is filtered for that one token, as before.

## Results (run 2026-11-21)

| ID | Verdict |
|---|---|
| P1 | **PASS**: 221/221 identical, new defaults vs the previous build (`results_gate_P1_default.json`) |
| P2 | **PASS**: 221/221 identical, `CLUSTERSTREAM=0` vs the previous build (`results_gate_P2_off.json`) |
| P3 | **PASS**: 3/3 identical (company scale 32: 35,815 lines; scale 64: 71,178; gates 1600: 2,122) |
| P4 | **PASS**: company scale 64 with defaults, 256 MB peak, 19.7 s (previous build 8,350 MB, 48.5 s; `/usr/bin/time`) |
| P5 | **PASS**: `make test` (30/30 kit checks, 63 SDK/MCP tests) and `make sanitize` (63/63) |

Other P3 measurements: company scale 32 went from 2,129 MB / 12.7 s to 130 MB / 6.1 s; gates 1600 from 8,252 MB /
27.2 s to 72 MB / 7.0 s.
