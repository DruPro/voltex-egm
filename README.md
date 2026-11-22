<div align="center">

<img src="media/images/voltex-egm-logo.png" alt="Voltex EGM" width="640">

### A CPU-only, evidential grammar memory knowledge engine

Learns rules from plain facts · answers with proofs · says when it doesn't know.<br>
**No GPU. No training. No API keys.**

<br>

[![Version](https://img.shields.io/badge/version-2.2.1-ff2d95?style=for-the-badge)](https://github.com/DruPro/voltex-egm/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-ff2d95?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-1a1a1a?style=for-the-badge&logo=python&logoColor=ff2d95)](pyproject.toml)
[![C++](https://img.shields.io/badge/C%2B%2B-17-1a1a1a?style=for-the-badge&logo=cplusplus&logoColor=ff2d95)](src/voltex2.cpp)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-1a1a1a?style=for-the-badge)](#installation)
[![MCP](https://img.shields.io/badge/MCP-ready-ff2d95?style=for-the-badge)](docs/MCP.md)

<br>

[**Installation**](#installation) &nbsp;•&nbsp;
[**See it work**](#see-it-work) &nbsp;•&nbsp;
[**Quick start**](#five-minute-tour) &nbsp;•&nbsp;
[**Evaluating**](#evaluating) &nbsp;•&nbsp;
[**MCP server**](#serving-it-to-an-llm-mcp) &nbsp;•&nbsp;
[**Python SDK**](#python-sdk) &nbsp;•&nbsp;
[**Docs**](#documentation)

</div>

---

## Overview

<img src="media/images/voltex-egm-mascot.png" alt="Voltex EGM mascot" width="260" align="right">

**Voltex EGM** is a knowledge engine that **learns rules from facts** and answers with **proofs**. Give it plain
lines like `ana lives in porto` or `g7 has kind xor`. It finds the relations, discovers the rules that hold between
them (inverse, chains, multi-premise paths, decision trees), and derives what was never stated. Every answer
carries its evidence. When nothing supports an answer, it says *unknown*, not *no*.

- **Learns rules; you don't write them.** Rules are counted from the facts and scored against base rates.
- **Every answer has a proof** back to stated facts, and a tier:
  - *law*: the rule held, with high reliability, wherever the answer was known;
  - *tendency*: a weighted guess.
- **The learned rules can be run as a program.** Taught by examples, it computed adders, cellular automata and a
  Turing machine's steps (see [Mimic](lang/mimic)).
- **Runs on any CPU.** A single C++17 file with no dependencies, plus a Python SDK, a CLI and an MCP server for LLM
  agents.
- **Measured honestly.** Every number on this page comes from a study in `studies/`, with its failures next to its
  wins. Most are pre-registered; exploratory results are labelled as such in their reports (`docs/EVALUATION.md`).

<br clear="right">

---

## See it work

```bash
make                                   # builds the engine (a few seconds)
python3 lang/mimic/play.py             # a guided tour, then a prompt where you teach it your own
```

The playground teaches the engine with examples and lets you watch it work:
- **A full adder from three shown truth tables,** plus a proof of 1 + 1 + 1 back to the inputs.
- **A Turing machine from three shown transitions:**

```
   _  1  1  1 [1] _    start in carry
   _  1  1 [1] 0  _    step 1: carry read 1 -> write 0, left, go carry
   ...
   _ [_] 1  0  0  0  0  _    step 5: carry read _ -> write 1, left, go halt
   halted after 5 steps
```

- **Rule 110, drawn from its 8 cases:**

```
   ·······························█
   ······························██
   ·····························███
   ····························██·█
   ···························█████
```

- **What it does with a case it was never shown:** it stops with *UNKNOWN* instead of guessing.

Nothing in the playground knows what XOR or a Turing machine is; it only draws what the engine answers. The
language behind it is **[Mimic](lang/mimic/README.md)**.

---

## What you can build with it

| Use | What it gives you | Evidence |
|---|---|---|
| **A code knowledge base for an agent** | extract facts from a codebase (`egm extract python`), serve them over MCP; the agent gets answers with proofs, and "unknown" when the facts don't say | [Sonnet sessions](docs/AGENT_SESSIONS.md): 3/3 hidden definitions found, 6/6 callers, a root cause found in 22 calls |
| **Rule discovery in structured data** | the rules a table implies, with their exceptions | Unicode tables: 96.2% of new facts true against `unicodedata`; most errors were Unicode's own exceptions ([findings](docs/STRESS_FINDINGS.md)) |
| **Exact reasoning over parser output** | multi-hop ancestry, 3-premise paths, decision-table rules learned from code alone | Python stdlib: 98.8% of hidden facts recovered, every law-tier answer correct; replicated on 1M lines ([strengths](docs/STRENGTHS.md)) |
| **Programs taught by example** | functions, state machines, circuits and automata whose meaning is learned; inspectable rules, proofs, honest stops | [Mimic](lang/mimic/REPORT.md): 14/14 definitions learned, 0 wrong results; [learned programs](docs/LEARNED_PROGRAMS.md) |
| **Knowledge that changes** | snapshots from sources; old values become history; disagreements and stale conclusions are flagged | [SDK](docs/SDK.md), `egm observe` |

---

## A fair assessment

**Where it is strong**
- **Exact or consistent facts with real rules:** code structure, schemas, relational tables, circuits. There, every
  law-tier answer has been right in the studies: 5,829 of 5,829, and 17,265 of 17,269 on third-party code.
- **Explanation:** every derived fact has a proof, and every rule's supporting examples can be listed.
- **Calibrated caution:** law-tier precision held at 0.988 or better on every controlled world. When it lacks
  evidence it abstains, and an empty answer is reported as unknown.
- **Small, fast, local:** no GPU, no API keys. Questions on a built knowledge base take under a millisecond.

**Where it is weak**
- **Tendency-tier answers are guesses.** Their precision ranged from 0.03 to 1.00 across worlds. Use `strict=True`
  or `TENDENCYSTEPS 0` for answers you act on.
- **Noisy or sparse data** can let weak rules flood the answers: 1.15 million derived dpkg facts at the defaults,
  4% true. Settings matter per dataset ([choosing settings](docs/CHOOSING_SETTINGS.md)).
- **General rules can outvote exact exceptions** (`classmethod` versus "methods bind `self`").
- **Rebuild cost:** learning reruns after changes. `REFRESH` keeps learned rules across small changes, but every
  change still re-runs inference over everything.
- **It needs examples:** about 64 per row for learned tables. A relation needs at least 3 facts. A name seen once
  can't fill a learned slot.

**What it is not**
- Not a language model: it doesn't generate prose or understand text beyond its fact templates.
- Not a theorem prover or a database: it finds regularities in evidence, and doesn't replace an exact query.
- Not Turing complete on its own: it computes bounded, laid-out computations. Unbounded runs need a loop around it,
  such as Mimic.

---

## Installation

> **Requirements:** a C++17 compiler and Python 3.8+ (standard library only).

<table>
<tr>
<th>Python (SDK + CLI)</th>
<th>From source (CLI + engine on <code>PATH</code>)</th>
</tr>
<tr>
<td valign="top">

```bash
# straight from the repo, at a tag
pip install git+https://github.com/DruPro/voltex-egm.git@v2.2.1

# or from a checkout
pip install .

egm doctor
```

</td>
<td valign="top">

```bash
make                          # builds build/voltex2
make test                     # kit, SDK and MCP test suites
make install PREFIX=~/.local  # egm + voltex2 → ~/.local/bin
egm doctor                    # finds the engine, runs its self-test
```

</td>
</tr>
</table>

Without installing, run `bin/egm` from the checkout. To use another engine build, set
`VOLTEX=/path/to/voltex2`. `make uninstall PREFIX=~/.local` removes everything that was installed.

---

## Five-minute tour

```bash
egm extract python mypkg=path/to/mypkg -o mypkg      # mypkg.txt (facts) + mypkg.truth.json
egm build mypkg.txt -o mypkg.vtx                     # ingest once, save
egm ask mypkg.vtx "? calls mypkg__connect"           # who calls connect
egm ask mypkg.vtx "mypkg__Client raises ?" --strict  # stated facts and law-tier rules only
egm ask mypkg.vtx "mypkg__Client raises ?" --json    # structured, with proofs
egm rules mypkg.vtx                                  # what relations and rules it learned
```

| Concept | Convention |
|---|---|
| Function `f` | `mypkg__f` |
| Method `m` of class `C` | `mypkg__C_m` |
| Module `mypkg/a/b.py` | `mypkg__a__b` |
| Slot to fill | `?` |

Facts can come from anywhere as plain lines of the form `A relation B`, with one name per slot and
no spaces in names.

> [!NOTE]
> A relation is learned once it has **at least 3 facts with at least 2 different names in each
> slot**. Below that, `egm ask` says so instead of returning nothing.

---

## Evaluating

```bash
egm questions mypkg.truth.json -o qs --seed 7        # qs/questions.json (public), qs/key.json (hidden)
egm eval mypkg.vtx qs/key.json --both                # scripted solver, both policies, 0 tokens
egm answer mypkg.vtx qs/questions.json -o a.json     # or produce answers ...
egm score qs/key.json a.json -o score.json           # ... and score them, including ones an LLM wrote
```

There are six question kinds: `lookup`, `callers`, `caller_modules`, `raises_1hop`, `grandparent`
and `imports`. A single value is scored by exact match and a list by F1. With `--expect F1`, `eval`
and `score` exit 1 on a mismatch, which is useful in CI.

> [!WARNING]
> Keep `key.json` away from any model you are evaluating.

---

## Changing data

```bash
egm observe kb.vtx --source repo --record net.py --time 2 -f "a calls b" -f "a calls c"
```

A **`snapshot`** (the default) is everything that record says now. Facts it no longer states become
history, for example `historical: held per repo from t=1 until t=2`. A **`partial`** observation
only adds facts.

---

## Serving it to an LLM (MCP)

```bash
egm mcp /abs/path/kb.vtx                        # read-only MCP server over stdio
claude mcp add egm -- egm mcp /abs/path/kb.vtx  # e.g. in Claude Code
```

| Mode | Tools |
|---|---|
| Read-only (default, strict) | `egm_relations` · `egm_ask` · `egm_values` · `egm_ask_many` · `egm_history` · `egm_conflicts` · `egm_infer` |
| `--writable` adds | `egm_observe` · `egm_ingest` · `egm_save` |

Setup for other clients and the protocol details are in **[docs/MCP.md](docs/MCP.md)**.

---

## Python SDK

```python
import egm

with egm.open("mypkg.vtx") as kb:                      # loaded once; each call is a pipe round trip
    for f in kb.ask("? calls mypkg__connect"):
        print(f.subject, f.status, f.tier, f.because)
    kb.values("mypkg__Client raises ?", strict=True)  # just the names
    kb.history("mypkg__Client calls ?")               # what it used to call
    kb.rules(), kb.relations(), kb.infer_all(), kb.conflicts()
    kb.predict("mypkg__Client"), kb.generate(), kb.sample(3)
```

Every engine command has a typed method that returns dataclasses (`Fact`, `Rule`, `Relation`,
`Prediction`, `Category`, `Conflict`). Errors derive from `egm.EgmError`. The full reference,
including an LLM-tool example, is in **[docs/SDK.md](docs/SDK.md)**.

---

## Other commands

| Command | Purpose |
|---|---|
| `egm shell kb.vtx` | Interactive engine session (`ASK`, `RELATIONS`, `INFER ALL`, `HELP` …) |
| `egm run kb.vtx cmds.txt` | Raw engine commands from a file; `--save` keeps the result |
| `egm bench facts.txt` | Timings for ingest, inference build and queries |
| `egm tune facts.txt -o tuned.json` | Pick settings for one dataset from the dataset itself (experimental; `studies/noise`) |

---

## Reproducing the published numbers

```bash
make repro
```

| Check | Expected mean F1 |
|---|:---:|
| Requests use case: EGM-script over Haiku's 597 extracted facts | **0.993** |
| Tokenomics S / M / L, default policy | **1.000 / 0.972 / 1.000** |
| Tokenomics S / M / L, strict policy (exploratory) | **1.000 / 1.000 / 1.000** |

The data is in [`examples/`](examples). The questions and keys are the ones used in the studies.

---

## Results at a glance

Most of these are pre-registered (the agent sessions and Mimic's `refresh` mode are exploratory, and labelled so).
The full reports hold the failures as well as the wins.

| Study | Result | Failures and limits |
|---|---|---|
| [Python stdlib, exact facts](docs/STRENGTHS.md) | 5,829 / 5,901 hidden facts recovered; every law-tier answer correct; replicated on 1M lines of Debian packages (97.9%) | the 4 false law-tier answers came from an extractor gap; exceptions lost to general rules |
| [Stress bench](docs/STRESS_FINDINGS.md), 31 datasets | Unicode rules 96.2% true; precise multi-step proofs on real code | dpkg floods at the defaults; `DEPTH 0` ran out of memory on wide graphs |
| [Agent sessions](docs/AGENT_SESSIONS.md) (Sonnet over MCP) | definitions, callers and a root cause found, each with proofs | 1 of 7 inferred exception sources right (the agent flagged them as weak) |
| [Computation](docs/LEARNED_PROGRAMS.md) | NAND-only adders 3,330 / 3,330 wires; Rule 110 720 / 720 cells | a base-rate shortcut rule cost 47 wrong values in one seed (fixed by law-only proofs) |
| [Learned programs](docs/LEARNED_PROGRAMS.md) | state machine, recursion, adders, automaton: 2,708 / 2,708 in one pass, runtime state never learned from, proofs traced to examples | chunked execution helped 7×, not the predicted 10× |
| [Mimic](lang/mimic/REPORT.md) | 14 / 14 definitions learned, 0 wrong results in 4 modes | OBSERVE snapshot loss; programs sharing values interfered until namespaced |
| [Engine changes](studies/refresh_trees/RESULTS.md) | `REFRESH` for tree rules: 109 / 109 steps identical to relearning; byte-identical when off | 2.5-2.7× faster, not the predicted 3× |
| [Evaluation baseline](studies/eval/BASELINE.md) | law-tier precision ≥ 0.988 on every controlled world; scorecard deterministic | tendency-tier precision is not calibrated |

Engine changes in this cycle, each pre-registered and shown byte-identical with the change off (the 221-cell
regression gate, plus the 294-cell stress bench for the two later changes):
- `CLUSTERSTREAM` (on by default): 244,444 facts in 256 MB instead of 8,350 MB.
- A cheaper category loop: up to 9× faster builds.
- `REFRESH` for tree rules.

---

## How it works, in one paragraph

Facts are stored exactly in a compressed grammar. Words that appear in similar places form categories. Repeated
sentence shapes become relations. Rules are counted between relations and accepted only when they beat the base
rate. Accepted rules are applied round after round to derive new facts, each with a proof and a tier.

Learning (rule mining) reads stated facts only. Inference applies a fixed rule list. So a derived value never
becomes evidence, and the learned rules can act as a program ([THEORY.md](docs/THEORY.md),
[LEARNED_PROGRAMS.md](docs/LEARNED_PROGRAMS.md)).

---

## Known limitations

<details>
<summary><b>Expand</b></summary>

<br>

- **Cold start.** A name seen in only one fact can't fill a learned slot. Relations need 3+ facts.
- **Weak rules.** Tendency-tier rules can be wrong. Use `--strict` (or `TENDENCYSTEPS 0`) when precision matters.
- **Rule shapes.** Learned rules are inverses, chains, paths of up to 8 premises (`CHAIN`), group conditions
  (`CONDITIONS`) and trees (`TREES`).
  - A same-direction copy `r(a,b) ⇒ s(a,b)` isn't a shape: state the inverse instead.
  - Tree targets can have at most 8 distinct values.
- **Categories can drop facts silently.** A value that falls outside its slot's category takes its facts out of the
  relation, with no warning. Keep unrelated domains' values distinct ([Mimic report](lang/mimic/REPORT.md) §5.3).
- **OBSERVE snapshots** can lose a record's current state after 13-26 restatements when plain facts also name the
  entity (`lang/mimic/repro_observe_loss.py`).
- **Rebuild cost.** Changes re-run learning, unless `REFRESH` applies (small changes, no new words, not with
  `CHAIN 3+` or `CONDITIONS`). Inference always re-runs in full.
- **Storage.** The observation log roughly doubles storage on heavily revised data.
- **Memory at exit.** The grammar has no destructor. The sanitizer build finds no memory errors or undefined
  behaviour, but reports the memory still allocated at exit.
- **Extraction** is built in for Python only (static, never executes the code). For other languages, emit
  `A relation B` lines.

</details>

---

## Project layout

```text
voltex-egm/
├── src/voltex2.cpp        # the engine (single file, no dependencies)
├── egm/                   # SDK (engine, model, parse, errors), extractor, bench, tune, shard, MCP server, CLI
├── bin/egm                # launcher (works from a checkout or an install)
├── lang/mimic/            # Mimic: a language taught by example (interpreter, playground, examples, bench, report)
├── docs/                  # references, guides and research reports (table below)
├── examples/              # Requests (Haiku facts) and tokenomics (S, M, L) with keys
├── studies/               # pre-registered studies, each with its plan, deviations, results and tools
├── tests/                 # run_tests.py (kit), test_sdk.py, test_mcp.py, test_mimic.py
├── media/images/          # logo and mascot
├── pyproject.toml         # pip packaging
└── setup.py               # compiles the engine during pip install
```

---

## Documentation

| Document | Description |
|---|---|
| [lang/mimic/README.md](lang/mimic/README.md) | Mimic: the language and the playground |
| [lang/mimic/REPORT.md](lang/mimic/REPORT.md) | Mimic research report: encoding, execution modes, bench, what it revealed about the engine |
| [docs/LEARNED_PROGRAMS.md](docs/LEARNED_PROGRAMS.md) | Research report: learned rules as programs (computation, the harness, inferred programs, `REFRESH` for trees) |
| [docs/SDK.md](docs/SDK.md) | Python SDK reference, including an LLM-tool example |
| [docs/MCP.md](docs/MCP.md) | MCP server: client setup, tools, protocol |
| [docs/SETTINGS.md](docs/SETTINGS.md) | Every engine setting: default, owning layer, stable or experimental |
| [docs/CHOOSING_SETTINGS.md](docs/CHOOSING_SETTINGS.md) | Which settings to use for what you're trying to do, when not to, and what each costs |
| [docs/EVALUATION.md](docs/EVALUATION.md) | How engine changes are judged: capability matrix, protocol, improvement vs regression |
| [docs/STRENGTHS.md](docs/STRENGTHS.md) | The engine at its best: exact facts from two Python codebases, complete truth |
| [docs/STRESS_FINDINGS.md](docs/STRESS_FINDINGS.md) | What it learned from real code, Unicode and Debian package data, with proofs and errors |
| [docs/AGENT_SESSIONS.md](docs/AGENT_SESSIONS.md) | Recorded Sonnet sessions over MCP, each claim checked against hidden facts |
| [docs/BUILDING_A_LAYER.md](docs/BUILDING_A_LAYER.md) | Building an analysis layer: fact design, hidden keys, settings, reading rules |
| [docs/DATA_DESIGN.md](docs/DATA_DESIGN.md) | Designing data for deliberate inference: rule shapes, law vs tendency |
| [docs/THEORY.md](docs/THEORY.md) | Principles and theory: the layers, emergent behavior, information limits |
| [studies/](studies/) | Every pre-registered study, in order |

---

## Changelog

### Unreleased

- **Mimic and its playground** (`lang/mimic`):
  - a language taught by example: functions, Turing machines, circuits and automata;
  - `play.py`, a guided tour and a prompt;
  - a `refresh` mode that keeps learned rules while programs run;
  - machine values namespaced per machine.
- **Engine:** `REFRESH` re-attaches every relation a rule references and works with `TREES`. Learned tree programs
  run step by step without relearning (`studies/refresh_trees`). It is off by default and byte-identical when off.
- **Studies:**
  - `studies/compute`: bounded computation from learned gates;
  - `studies/harness`: a harness supplies memory and a clock;
  - `studies/inferred_program`: learned rules executed as programs;
  - `studies/strengths`: exact code facts, replicated;
  - `studies/eval`: evaluation framework and baseline;
  - `studies/architecture`: designed, paused.
- **SDK and MCP:**
  - `egm.tune(..., settings=..., expanded=True)`;
  - empty answers say "unknown, not false" and name any cap;
  - `egm extract python` drops a definition named like a module.
- **Earlier on this cycle:**
  - `CLUSTERSTREAM` on by default;
  - the cheaper category loop;
  - `egm.shard`;
  - docs `CHOOSING_SETTINGS`, `BUILDING_A_LAYER`, `AGENT_SESSIONS`, `STRESS_FINDINGS`, `STRENGTHS`, `EVALUATION`,
    `LEARNED_PROGRAMS`.

### 2.2.1

Three additive engine changes. None of them changes any answer, and `make repro` checks this.

- Output is flushed after every command, so piped sessions stay interactive.
- New `--version` flag.
- New `ECHO` command, which the SDK uses to mark the end of each reply. An earlier draft used
  `FIND <marker>` for this, but a `FIND` of a missing record could imitate the marker and shift
  every later reply by one.

---

## License

Distributed under the **Apache License 2.0**. See [`LICENSE`](LICENSE) for details.

<div align="center">
<br>
<img src="media/images/voltex-egm-logo.png" alt="Voltex EGM" width="200">
<br>
<sub>Built by the Voltex EGM team</sub>
</div>
