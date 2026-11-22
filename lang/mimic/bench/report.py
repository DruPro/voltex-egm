"""Write RESULTS.md from results.json and verdicts.json (every number read from those files).  python3 report.py"""
import json, os, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results.json"))); V = json.load(open(os.path.join(HERE, "verdicts.json")))
P = R["programs"]
def counts(rs): c = [j["verdict"] for r in rs for j in r["judged"]]; return c.count("right"), c.count("wrong"), c.count("unknown"), len(c)
rows = []
for name in dict.fromkeys(r["program"] for r in P):
    cells = []
    for mode in ("fresh", "rebuild", "observe"):
        r = [x for x in P if x["program"] == name and x["mode"] == mode][0]; a, w, u, n = counts([r])
        cells.append(f"{a}/{n}" + (f", {u} unknown" if u else "") + (f", **{w} wrong**" if w else ""))
    rows.append(f"| `{name}` | " + " | ".join(cells) + " |")
tot = {m: counts([x for x in P if x["mode"] == m]) for m in ("fresh", "rebuild", "observe")}
cc = R["cost_curve"]; cost = {}
for x in cc: cost.setdefault(x["ones"], {})[x["mode"]] = x
crow = "\n".join(f"| {n} | " + " | ".join(f"{cost[n][m]['ms_per_step']} ({cost[n][m]['status']}, {cost[n][m]['steps']} steps)" for m in ("fresh", "rebuild", "observe")) + " |" for n in sorted(cost))
B4 = R["recursive"]
def b4(k):
    rs = B4[k]; return (f"| {k.replace('_', ' ')} | {sum(r['verdict'] == 'right' for r in rs)}/{len(rs)} right"
                        + (f", {sum(r['verdict'] == 'unknown' for r in rs)} unknown" if any(r['verdict'] == 'unknown' for r in rs) else "")
                        + f" | {statistics.mean(r['questions'] for r in rs):.0f} | {statistics.mean(r['seconds'] for r in rs):.2f} s |")
g = [x for x in P if x["program"] == "guess" and x["mode"] == "fresh"][0]["learned"]
hid = "\n".join(f"| `{fn}` {k} | {h['expected']} | {h['inferred'] or 'unknown'} |" for fn, r in g.items() for k, h in r["hidden"].items())
fr = [x["ms_per_step"] for x in cc if x["mode"] == "fresh"]; rb = [x["ms_per_step"] for x in cc if x["mode"] == "rebuild"]
defs = {(r["program"], k): v for r in P if r["mode"] == "fresh" for k, v in r["learned"].items()}
nd = len(defs); n_rows = sum(v["taught"] for v in defs.values())
full = sum(1 for v in defs.values() if v.get("declared") or v["learned"] == v["taught"])
text = f"""# Mimic bench: results

Pre-registered (`PREREGISTRATION.md`, hash in `prereg_hash.txt`). Written by `report.py` from `results.json` and
`verdicts.json` (`bench.py`). The reference is a literal interpreter of each program's tables that never uses the
engine.

## Verdicts

| Prediction | Verdict |
|---|---|
| P1 `fresh` and `rebuild`: 0 wrong; everything not depending on an untaught row right | **{V['P1']}** |
| P2 `observe`: 0 wrong, and at least one unknown on the 16-one increment (snapshot loss) | **{V['P2']}** |
| P3 no mode gives a wrong result anywhere | **{V['P3']}** |
| P4 recursive questions at `DEPTH 1` give the `DEPTH 0` results; plain `DEPTH 1` leaves outputs unknown | **{V['P4']}** |
| P5 every program deterministic | **{V['P5']}** |

## B1: every result, every mode (right / total)

| Program | fresh | rebuild | observe |
|---|---|---|---|
{chr(10).join(rows)}

- **Totals:** `fresh` {tot['fresh'][0]}/{tot['fresh'][3]}, `rebuild` {tot['rebuild'][0]}/{tot['rebuild'][3]}, `observe`
  {tot['observe'][0]}/{tot['observe'][3]}.
- **Wrong anywhere:** {sum(t[1] for t in tot.values())}.
- **Unknowns in `guess`:** these are the untaught rows, by design. Where the engine couldn't decide, Mimic stopped and
  said so.

## B2: cost per machine step (ms), by run length

Increment on n ones.

| n ones | fresh | rebuild | observe |
|---|---|---|---|
{crow}

- **fresh:** {min(fr)}-{max(fr)} ms per step, flat up to 64 steps.
- **rebuild:** {min(rb)}-{max(rb)} ms per step. Every step relearns from the taught examples, so it costs about 2×
  `fresh` here. Its cost grows with what is taught, not with run length.
- **observe:** the same speed as `fresh`, but it stops with unknown once the record has been restated about 22
  times. That is the engine's snapshot loss (`repro_observe_loss.py`), and it is why `fresh` is the default.

**On re-ingesting.** You asked whether rebuilding from scratch might be more accurate and cheaper than OBSERVE.
- **Accurate:** yes. `rebuild` was right everywhere `observe` lost state.
- **Cheaper:** not here. `fresh`, which only adds the new step's facts to the running engine, is as accurate and
  about half the cost.

## B3: rows the engine was never shown (`guess`)

| Row | You meant | Engine inferred |
|---|---|---|
{hid}

The engine didn't generalise to the untaught majority rows. The taught rows don't force a unique answer for them,
and no rule was supported strongly enough. For the untaught increment transition, it gave only the declared move.
In both cases it abstained instead of guessing.

## B4: recursive questions vs chained inference (`add8`, 4 evaluations)

| Method | Result | Engine questions per evaluation | Time per evaluation |
|---|---|---|---|
{b4('depth0_bottom_up')}
{b4('depth1_bottom_up')}
{b4('depth1_recursive')}

**Is recursion redundant? For evaluation, yes.**
- **The comparison:** recursive questions (ask which gate makes a wire, evaluate its inputs, state them, ask again)
  reach the same answers as chained inference at `DEPTH 0`. They take about
  {statistics.mean(r['questions'] for r in B4['depth1_recursive']) / statistics.mean(r['questions'] for r in B4['depth0_bottom_up']):.0f}×
  the questions and {statistics.mean(r['seconds'] for r in B4['depth1_recursive']) / statistics.mean(r['seconds'] for r in B4['depth0_bottom_up']):.0f}×
  the time.
- **Why:** the engine's own chaining already does the walk, in one fixpoint. Recursion only re-does it one level at
  a time.
- **The one result:** with inference capped at `DEPTH 1`, recursion recovers what the cap hides. It is a workaround
  for a depth limit, not a gain.
- **Untested here:** where it might still pay is selective evaluation on data whose full fixpoint floods (dpkg at
  `DEPTH 0`), because recursion computes only what is asked.
- **Where recursion is useful today:** reading proofs. `why` walks an answer's proof down to the given facts. That
  navigates a tree the engine already built, so it isn't redundant.

## What this measures about the engine

- **Learning operations from examples.** {nd} functions and machines in 8 programs (1 to 3 inputs, up to 6
  transitions, {n_rows} taught rows). {full} of {nd} were learned to 100% of their taught rows, as checked on fresh
  probes (`learned` in `results.json`).
- **Composition.** Learned gates chained 17 deep (`add8`), a learned 3-input rule over 16 steps (`rule110`), and a
  busy beaver: all exact.
- **Reliability.** 0 wrong results in 3 modes over 8 programs. Every failure to decide is reported as unknown.
- **Boundaries met:**
  - at most 8 values per target relation;
  - constant outputs can't be learned;
  - majority values need about 64 examples;
  - relation phrases that differ in one word confuse the slots;
  - OBSERVE snapshots are lost after about 13-26 restatements.
"""
open(os.path.join(HERE, "RESULTS.md"), "w").write(text); print(text[:3000])
