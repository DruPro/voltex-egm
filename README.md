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
│   └── MCP.md             # MCP server: client setup, tools, protocol
├── examples/              # Requests (Haiku facts) and tokenomics (S, M, L) with keys
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

---

## Changelog

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
