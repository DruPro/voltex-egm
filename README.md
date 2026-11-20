# EGM kit (Voltex 2.2.1)

A CPU-only knowledge engine plus one command, `egm`, for the whole loop: extract facts, build a
knowledge base, query it, and score it against a question key. No GPU, no training, no API keys.

## Install

Needs a C++17 compiler and Python 3.8+ (standard library only).

**Python (SDK + CLI):**

    pip install git+https://github.com/USER/REPO.git@v2.2.1   # straight from the repo, at a tag
    pip install .                                             # or from a checkout
    egm doctor

**From source (CLI + engine on PATH):**

    make                          # builds build/voltex2
    make test                     # 30 kit checks, 29 SDK tests, 8 MCP tests, including the published numbers
    make install PREFIX=~/.local  # installs egm and voltex2 into ~/.local/bin (no sudo)
    egm doctor                    # confirms the engine is found and passes its self-test

Without installing, use `bin/egm` from the checkout. To use another engine build, set
`VOLTEX=/path/to/voltex2`. `make uninstall PREFIX=~/.local` removes everything it installed.

## Five-minute tour

    egm extract python mypkg=path/to/mypkg -o mypkg      # mypkg.txt (facts) + mypkg.truth.json
    egm build mypkg.txt -o mypkg.vtx                     # ingest once, save
    egm ask mypkg.vtx "? calls mypkg__connect"           # who calls connect
    egm ask mypkg.vtx "mypkg__Client raises ?" --strict  # stated facts and law-tier rules only
    egm ask mypkg.vtx "mypkg__Client raises ?" --json    # structured, with proofs
    egm rules mypkg.vtx                                  # what relations and rules it learned

Names are package-qualified: function `f` → `mypkg__f`, method `m` of class `C` → `mypkg__C_m`,
module `mypkg/a/b.py` → `mypkg__a__b`. A `?` marks the slot to fill.

Facts can come from anywhere, as plain lines of the form `A relation B` (one name per slot, no spaces
in names). A relation is learned once it has **at least 3 facts with at least 2 different names in
each slot**. Below that, `egm ask` tells you so instead of returning nothing.

## Evaluating

    egm questions mypkg.truth.json -o qs --seed 7        # qs/questions.json (public), qs/key.json (hidden)
    egm eval mypkg.vtx qs/key.json --both                # scripted solver, both policies, 0 tokens
    egm answer mypkg.vtx qs/questions.json -o a.json     # or produce answers ...
    egm score qs/key.json a.json -o score.json           # ... and score them, including ones an LLM wrote

Six question kinds: lookup, callers, caller_modules, raises_1hop, grandparent, imports. Scores are
exact match for one value and F1 for lists. `--expect F1` makes `eval` and `score` exit 1 on a
mismatch, for CI. Keep `key.json` away from any model you are evaluating.

## Changing data

    egm observe kb.vtx --source repo --record net.py --time 2 -f "a calls b" -f "a calls c"

A `snapshot` (the default) is everything that record says now: facts it no longer states become
history (`historical: held per repo from t=1 until t=2`). A `partial` observation only adds.

## Serving it to an LLM (MCP)

    egm mcp /abs/path/kb.vtx                       # read-only MCP server over stdio
    claude mcp add egm -- egm mcp /abs/path/kb.vtx # e.g. in Claude Code

The tools are `egm_relations`, `egm_ask`, `egm_values`, `egm_ask_many`, `egm_history`,
`egm_conflicts` and `egm_infer`; `--writable` adds `egm_observe`, `egm_ingest` and `egm_save`.
They are strict by default. Setup for other clients and the protocol details are in
[docs/MCP.md](docs/MCP.md).

## Other commands

    egm shell kb.vtx          # interactive engine session (ASK, RELATIONS, INFER ALL, HELP ...)
    egm run kb.vtx cmds.txt   # raw engine commands from a file, --save to keep the result
    egm bench facts.txt       # ingest, inference build and query timings

## Python SDK

    import egm
    with egm.open("mypkg.vtx") as kb:                      # loaded once; each call is a pipe round trip
        for f in kb.ask("? calls mypkg__connect"):
            print(f.subject, f.status, f.tier, f.because)
        kb.values("mypkg__Client raises ?", strict=True)  # just the names
        kb.history("mypkg__Client calls ?")               # what it used to call
        kb.rules(), kb.relations(), kb.infer_all(), kb.conflicts()
        kb.predict("mypkg__Client"), kb.generate(), kb.sample(3)

Every engine command has a typed method that returns dataclasses (`Fact`, `Rule`, `Relation`,
`Prediction`, `Category`, `Conflict`), and errors derive from `egm.EgmError`. The full reference,
including an LLM-tool example, is in [docs/SDK.md](docs/SDK.md).

## Reproducing the published numbers

    make repro

| Check | Expected mean F1 |
|---|---|
| Requests use case: EGM-script over Haiku's 597 extracted facts | 0.993 |
| Tokenomics S / M / L, default policy | 1.000 / 0.972 / 1.000 |
| Tokenomics S / M / L, strict policy (exploratory) | 1.000 / 1.000 / 1.000 |

The data is in `examples/`. The questions and keys are the ones used in the studies.

## Known limitations

- **Cold start.** A name seen in only one fact cannot fill a learned slot. Relations need 3+ facts.
- **Weak rules.** Tendency-tier rules can be wrong, and at corpus M they cost 3–9 F1 points on fresh
  question sets. Use `--strict` when precision matters.
- **Strict-policy evidence.** On parser-built facts the strict policy is near-perfect by construction,
  because stated facts are the truth. Its real test is facts written by an LLM.
- **Storage.** The v2.2 observation log roughly doubles storage on heavily revised data.
- **Memory at exit.** The grammar has no destructor. The sanitizer build finds no memory errors or
  undefined behaviour, but it reports the memory still allocated at exit.
- **Extraction** is built in for Python only (static, never executes the code). For other languages,
  emit `A relation B` lines.

## Layout

    src/voltex2.cpp      the engine (single file, no dependencies)
    egm/                 the SDK (engine, model, parse, errors), extractor, bench (questions/solver/scoring), CLI
    docs/SDK.md          SDK reference
    docs/MCP.md          MCP server: client setup, tools, protocol
    bin/egm              launcher (works from a checkout or an install)
    examples/            Requests (Haiku facts) and tokenomics (S, M, L corpora) with keys
    tests/               run_tests.py (kit), test_sdk.py (SDK API); make test / repro / sanitize
    pyproject.toml, setup.py   pip packaging (setup.py compiles the engine)

## Changes in 2.2.1

Three additive engine changes, none of which changes any answer (`make repro` checks this):
output is flushed after every command, so piped sessions stay interactive; `--version`; and an
`ECHO` command, which the SDK uses to mark the end of each reply. (An earlier draft used
`FIND <marker>` for this, which a `FIND` of a missing record could imitate, shifting every later
reply by one.)
