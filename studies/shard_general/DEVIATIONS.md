# Deviations from PREREGISTRATION.md

1. **Single-engine memory not reported.** The harness read peak memory with `wait4` from inside Python, which
   includes the parent's high-water mark for small engines (see studies/scaling DEVIATIONS 4). The pre-registered
   "one engine's peak memory" descriptive figure is therefore omitted; no hypothesis depended on it.
2. **Mechanism tracing after the runs** (skew measurement, per-shard tree rules) is exploratory and labelled so in
   RESULTS.md.
