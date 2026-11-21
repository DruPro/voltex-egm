<div align="center">

<img src="media/images/voltex-egm-logo.png" alt="Voltex EGM" width="640">

### A CPU-only, evidential grammar memory knowledge engine

Extract facts · build a knowledge base · query it · score it — with one command.<br>
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
[**Quick start**](#five-minute-tour) &nbsp;•&nbsp;
[**Evaluating**](#evaluating) &nbsp;•&nbsp;
[**MCP server**](#serving-it-to-an-llm-mcp) &nbsp;•&nbsp;
[**Python SDK**](#python-sdk) &nbsp;•&nbsp;
[**Docs**](#documentation)

</div>

---

## Overview

<img src="media/images/voltex-egm-mascot.png" alt="Voltex EGM mascot" width="260" align="right">

**EGM** is a knowledge engine built on **Voltex**, a single-file C++ core with no dependencies. It
learns relations and rules from plain `A relation B` facts. It answers queries with proofs and
evidence tiers, and it keeps a history of how the facts changed over time.

- **Runs on any CPU.** It needs a C++17 compiler and Python's standard library, nothing else.
- **Every answer comes with its evidence.** Results carry status, tier and proof (`--json`), and `--strict` restricts them to stated facts and law-tier rules.
- **Learns rules from data.** Relations and inference rules are learned from the facts. You don't write them.
- **Tracks history.** Snapshot observations turn facts that a record no longer states into history.
- **Works with LLMs.** It ships a read-only MCP server and a typed Python SDK.
- **Measurable.** A built-in question generator, a scripted solver and a scorer reproduce the published numbers.

<br clear="right">

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

## Results on real workflows

From the stress study (`studies/stress`): 31 datasets, 295 runs, with 20% of each real dataset hidden as an answer
key.

**An agent using the engine** (Claude Sonnet 5.5 over `egm mcp`, engine tools only; recorded sessions, each claim
checked against the hidden facts: [docs/AGENT_SESSIONS.md](docs/AGENT_SESSIONS.md)):

| Task, on 125 real Python packages or the dpkg database | Result |
|---|---|
| Where is this function defined? (facts hidden from the engine) | 3 of 3 found by inference, each with its proof |
| Impact analysis: callers two levels up | 6 of 6 callers, with their modules |
| Where can this exception come from? | stated raisers and all 4 callers right; 1 of 7 inferred raisers right, which the agent flagged as weak leads |
| Why does inference derive a million facts? | root cause found (a reversed rule) in 22 engine calls, 100 s |

**What the engine learned with no rules given** ([docs/STRESS_FINDINGS.md](docs/STRESS_FINDINGS.md)):

| Data | Learned | Accuracy of new facts |
|---|---|---|
| Unicode tables (11,172 characters) | case pairs are inverses; case partners and decompositions share script, direction, category | 96.2% true against `unicodedata`; 40 of 50 errors are Unicode's own exceptions |
| Python code (64,763 facts) | a function lives where the functions it calls live (0.82 on 10,372 cases) | multi-step proofs; precision depends on settings |
| Debian packages (14,296 facts) | transitive dependencies | 87.6% true with `DEPTH 1`, 4.2% with the default `DEPTH 4` |
| Company and social data | team, manager, symmetric and inverse relations | precision 1.00 |

**Settings matter per dataset.** `TENDENCYSTEPS 0` takes Python packages from 0.010 to 0.963 precision but halves
recall on company data; `TREES 1` and `CHAIN 3` are the only way to answer gates and family trees. See
[docs/CHOOSING_SETTINGS.md](docs/CHOOSING_SETTINGS.md).

**Where it goes wrong:**
- On sparse or skewed data it can accept rules backed by few known cases. Inference then multiplies them: 1.15
  million dpkg facts at the defaults.
- `DEPTH 0` on wide graphs runs out of memory.
- Below the `MAXWORDS` cap, questions about rarer names come back empty, with no warning.

## Implementation results

| Change | Result |
|---|---|
| `CLUSTERSTREAM` (on by default) | Categories are built without listing every similar pair. Identical output on 221/221 regression cells. 244,444 facts: 8,350 MB, 48.5 s → 256 MB, 19.7 s |
| Cheaper joined check in the category loop | Identical output on 294/294 stress runs and 221/221 regression cells. Gates, 80,063 facts: 22.1 s → 2.4 s; code in three languages 10.6 s → 3.9 s |
| `egm.shard` (experimental) | Several engines for independent sources. Splitting one dataset is not general: it matched one engine on 2 of 6 world shapes ([studies/shard_general](studies/shard_general/RESULTS.md)) |

Every change was pre-registered, gated on byte-identical output, and run on every dataset
([studies/scaling](studies/scaling/PROMOTION.md), [studies/stress](studies/stress/RESULTS.md)).

---

## Known limitations

<details>
<summary><b>Expand</b></summary>

<br>

- **Cold start.** A name seen in only one fact cannot fill a learned slot. Relations need 3+ facts.
- **Weak rules.** Tendency-tier rules can be wrong. At corpus M they cost 3–9 F1 points on fresh
  question sets. Use `--strict` when precision matters.
- **Strict-policy evidence.** On parser-built facts the strict policy is near-perfect by
  construction, because the stated facts are the truth. Its real test is facts written by an LLM.
- **Storage.** The v2.2 observation log roughly doubles storage on heavily revised data.
- **Memory at exit.** The grammar has no destructor. The sanitizer build finds no memory errors or
  undefined behaviour, but it reports the memory still allocated at exit.
- **Extraction** is built in for Python only (static, never executes the code). For other
  languages, emit `A relation B` lines.

</details>

---

## Project layout

```text
voltex-egm/
├── src/voltex2.cpp        # the engine (single file, no dependencies)
├── egm/                   # SDK (engine, model, parse, errors), extractor, bench, CLI
├── bin/egm                # launcher (works from a checkout or an install)
├── docs/
│   ├── SDK.md             # SDK reference
│   ├── MCP.md             # MCP server: client setup, tools, protocol
│   ├── SETTINGS.md, CHOOSING_SETTINGS.md     # every setting; which to use when
│   └── BUILDING_A_LAYER.md, AGENT_SESSIONS.md, STRESS_FINDINGS.md
├── examples/              # Requests (Haiku facts) and tokenomics (S, M, L) with keys
├── studies/               # pre-registered studies; studies/stress holds the bench, layers and reports
├── tests/                 # run_tests.py (kit), test_sdk.py (SDK), test_mcp.py (MCP)
├── media/images/          # logo and mascot
├── pyproject.toml         # pip packaging
└── setup.py               # compiles the engine during pip install
```

---

## Documentation

| Document | Description |
|---|---|
| [docs/SDK.md](docs/SDK.md) | Python SDK reference, including an LLM-tool example |
| [docs/MCP.md](docs/MCP.md) | MCP server: client setup, tools, protocol |
| [docs/SETTINGS.md](docs/SETTINGS.md) | Every engine setting: default, owning layer, stable or experimental |
| [docs/CHOOSING_SETTINGS.md](docs/CHOOSING_SETTINGS.md) | Which settings to use for what you are trying to do, when not to, and what each costs (measured) |
| [docs/STRESS_FINDINGS.md](docs/STRESS_FINDINGS.md) | What the engine learned from real code, Unicode and Debian package data, with proofs and errors |
| [docs/AGENT_SESSIONS.md](docs/AGENT_SESSIONS.md) | Recorded Sonnet sessions over MCP: code navigation, impact analysis, debugging, each checked against hidden facts |
| [docs/BUILDING_A_LAYER.md](docs/BUILDING_A_LAYER.md) | Building an analysis layer (code, tables, logs): fact design, hidden keys, choosing settings, reading rules and proofs |
| [docs/DATA_DESIGN.md](docs/DATA_DESIGN.md) | Designing data for deliberate inference: rule shapes, law vs tendency, several engines together |
| [docs/THEORY.md](docs/THEORY.md) | Principles and theory: the layers, emergent behavior, information limits, design rules |
| [studies/](studies/) | Pre-registered studies: inference depth, multi-premise rules, configuration, scaling, sharding, the stress bench |

---

## Changelog

### Unreleased (branch `study/shard`)

- `CLUSTERSTREAM` is on by default. Same answers, far less memory on large vocabularies.
- Cheaper joined check in the category loop. Same answers; builds up to 9× faster on large vocabularies.
- `egm.shard` (experimental), for independent sources.
- New docs:
  - `CHOOSING_SETTINGS.md`;
  - `BUILDING_A_LAYER.md`;
  - `AGENT_SESSIONS.md`;
  - `STRESS_FINDINGS.md`.

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
