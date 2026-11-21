# Sonnet working with Voltex EGM: recorded sessions

These are real, unedited sessions: Claude Sonnet 5.5 connected to a Voltex EGM knowledge base through `egm mcp`, with no shell, files or web, only the engine's tools. The knowledge bases are 64,763 facts from 125 installed Python packages and 14,296 facts about installed Debian packages. 20% of each was hidden from the engine, so the answers can be checked. Tool results are truncated for space; Sonnet's answers are complete.

Recorded 5 sessions, $0.56 in total. Runner: `studies/stress/tools/sonnet_sessions.py`; recordings: `studies/stress/sonnet/*.json`.

## What the sessions show

- **The engine gives the model proofs, not just answers.** In every session Sonnet quoted the premises and the rule, said which facts were stated and which inferred, and set its confidence from the rule's tier and rate. A developer can check an answer in seconds.
- **Strict mode is the right default.** Sonnet always asked strict first, saw empty or partial results, and retried with strict off only when it needed tendencies, saying so in the answer.
- **The model stays honest when the engine is silent.** In the misconfigured run (0) it refused to guess module names from memory. Silence is only safe if the engine explains it, which it didn't.
- **Debugging the knowledge base works like debugging code.** Given only the tools, Sonnet traced a million-fact flood to one reversed rule in 22 engine calls and 100 s. The model's own claims still need checking: it called a true dependency a bug.
- **Sessions surface engine and tooling defects quickly.** Four small sessions found three: the silent MAXWORDS cap, unbounded tool results, and an extractor name collision.

## Defects the sessions found

- **A silent cap.** With `MAXWORDS` below the vocabulary, asking about a stated fact on a rarer name returns nothing, and neither `egm_relations` nor the empty result says why. Proposed: report `limits()` in `egm_relations` and add a note to empty results while a limit is active.
- **Unbounded results.** `egm_conflicts` and `egm_ask` returned 75,000 to 595,000 characters, more than the client accepts. Proposed: a `limit` with a total count, as `egm_infer` already has.
- **An extractor name collision.** `egm extract python` names a module `pkg__path` and a function `pkg__name`, so `cloudinit__subp` is both the module `subp.py` and its function `subp()`. 6 names collide this way and 62 facts read "X is defined in X". The learned rule "defined in a module that raises E ⇒ raises E" rests on them.

## 0. Code navigation, first attempt: the engine was misconfigured

*Goal:* Code navigation: find where functions live when that fact was never stated (all three are in the hidden key).  
*Knowledge base:* `code_realcode.txt`, settings `COVERAGE=0`  
*Session:* claude-sonnet-5-5, 5 engine calls, 7 turns, 25.5 s, $0.09

**Prompt**

> You are helping a developer navigate a large Python codebase (125 installed packages). The facts about it are in the egm knowledge base, available through the egm tools; names look like package__module__function. Answer using only those tools:
> 1. Which module is numpy's _block_slicing (numpy___block_slicing) defined in?
> 2. Which module is cloud-init's read_seeded (cloudinit__read_seeded) defined in?
> 3. Which module is wheel's WheelFile.writestr (wheel__WheelFile_writestr) defined in?
> For each, say whether the fact was stated or inferred, show the evidence chain, and how confident you are.

**Tool calls** (results truncated)

- `egm_relations` `{}`
  - → 1,702 chars: `{"relations": [{"template": "? calls ?", "facts": 8663}, {"template": "? is defined in ?", "facts": 8400}, {"template": "? imports ?", "facts": 6006}, {"template": "? raises ?", "facts": 2586}, {"template": "? inherits from ?", "facts": 1306}], "rules": [{"rule": "[? is defined in ?](a,b) & [? is de`
- `egm_ask_many` `{"patterns": ["numpy___block_slicing is defined in ?", "cloudinit__read_seeded is defined in ?", "wheel__WheelFile_writestr is defined in ?"]}`
  - → 266 chars: `{"strict": true, "results": [{"pattern": "numpy___block_slicing is defined in ?", "strict": true, "values": []}, {"pattern": "cloudinit__read_seeded is defined in ?", "strict": true, "values": []}, {"pattern": "wheel__WheelFile_writestr is defined in ?", "strict": true, "values": []}]}`
- `egm_ask_many` `{"patterns": ["numpy___block_slicing is defined in ?", "cloudinit__read_seeded is defined in ?", "wheel__WheelFile_writestr is defined in ?"], "strict": false}`
  - → 288 chars: `{"strict": false, "results": [{"pattern": "numpy___block_slicing is defined in ?", "strict": false, "values": []}, {"pattern": "cloudinit__read_seeded is defined in ?", "strict": false, "values": []}, {"pattern": "wheel__WheelFile_writestr is defined in ?", "strict": false, "values": ["wheel__wheelf`
- `egm_ask_many` `{"patterns": ["? calls numpy___block_slicing", "? calls cloudinit__read_seeded", "? calls wheel__WheelFile_writestr", "numpy___block_slicing calls ?", "cloudinit__read_seeded calls ?", "wheel__WheelFile_writestr calls ?"], "strict": false}`
  - → 517 chars: `{"strict": false, "results": [{"pattern": "? calls numpy___block_slicing", "strict": false, "values": []}, {"pattern": "? calls cloudinit__read_seeded", "strict": false, "values": []}, {"pattern": "? calls wheel__WheelFile_writestr", "strict": false, "values": ["wheel__WheelFile_write"]}, {"pattern"`
- `egm_ask_many` `{"patterns": ["wheel__get_zipinfo_datetime is defined in ?", "wheel__WheelFile_write is defined in ?", "wheel__WheelFile_writestr inherits from ?"], "strict": false}`
  - → 312 chars: `{"strict": false, "results": [{"pattern": "wheel__get_zipinfo_datetime is defined in ?", "strict": false, "values": ["wheel__wheelfile"]}, {"pattern": "wheel__WheelFile_write is defined in ?", "strict": false, "values": ["wheel__wheelfile"]}, {"pattern": "wheel__WheelFile_writestr inherits from ?", `

**Sonnet's answer**

I've run all three lookups and have what I need, so this is the write-up.

## 1. numpy `_block_slicing` (`numpy___block_slicing`)
- **Answer:** I can't tell from the knowledge base.
- **Evidence:** "numpy___block_slicing is defined in ?" returned nothing in strict mode or in non-strict mode. The knowledge base has no facts where it calls something or is called by something, so no inference rule has anything to work from.
- **Confidence:** None. I won't guess from the name. It could be `numpy.core.shape_base`, but that would come from my own memory, not from the knowledge base.

## 2. cloud-init `read_seeded` (`cloudinit__read_seeded`)
- **Answer:** I can't tell from the knowledge base.
- **Evidence:** Same as above. There are no "defined in", "calls" or "called by" facts in either mode.
- **Confidence:** None.

## 3. wheel `WheelFile.writestr` (`wheel__WheelFile_writestr`)
- **Answer:** `wheel__wheelfile`.
- **Status:** Inferred, not stated. Strict mode returned nothing. Only the non-strict query returned it, which includes tendency-tier inferences.
- **Evidence chain:**
  1. `wheel__WheelFile_writestr` calls `wheel__get_zipinfo_datetime`.
  2. `wheel__get_zipinfo_datetime` is defined in `wheel__wheelfile`.
  3. The "calls, then defined in" rule concludes that the caller is defined in the same module. This rule is tendency-tier and held about 67% of the time across 7,273 chains.
- **Corroboration:** `wheel__WheelFile_write` calls `wheel__WheelFile_writestr` and is itself defined in `wheel__wheelfile`. It's a sibling method of the same class, and it points to the same module.
- **Confidence:** Moderately high, around 85%. The rule alone is only about 67% reliable, but two independent chains agree and the class name matches the module name. I didn't find a stated fact to confirm it.

## Summary
| Item | Module | Status | Confidence |
|---|---|---|---|
| numpy `_block_slicing` | unknown | not in the knowledge base | none |
| cloud-init `read_seeded` | unknown | not in the knowledge base | none |
| wheel `WheelFile.writestr` | `wheel__wheelfile` | inferred (tendency-tier) | moderately high |

For items 1 and 2, the next step would be to read the installed source with grep, if you want me to.

**Checked against the hidden key and full facts**

| Claim | Verdict |
|---|---|
| wheel WheelFile.writestr → wheel.wheelfile, inferred | right (hidden fact) |
| numpy and cloud-init: "not in the knowledge base" | wrong, but honest: the engine ran with MAXWORDS 12,000 on a 40,918-word vocabulary, so stated facts about rarer names returned nothing and no warning reached Sonnet |
| declined to guess from the names | right call: it said a guess would come from its own memory, not the knowledge base |

## 1. Code navigation: where does this function live?

*Goal:* Code navigation: find where functions live when that fact was never stated (all three are in the hidden key).  
*Knowledge base:* `code_realcode.txt`, settings `COVERAGE=0 MAXWORDS=42000`  
*Session:* claude-sonnet-5-5, 6 engine calls, 8 turns, 19.6 s, $0.09

**Prompt**

> You are helping a developer navigate a large Python codebase (125 installed packages). The facts about it are in the egm knowledge base, available through the egm tools; names look like package__module__function. Answer using only those tools:
> 1. Which module is numpy's _block_slicing (numpy___block_slicing) defined in?
> 2. Which module is cloud-init's read_seeded (cloudinit__read_seeded) defined in?
> 3. Which module is wheel's WheelFile.writestr (wheel__WheelFile_writestr) defined in?
> For each, say whether the fact was stated or inferred, show the evidence chain, and how confident you are.

**Tool calls** (results truncated)

- `egm_relations` `{}`
  - → 1,499 chars: `{"relations": [{"template": "? is defined in ?", "facts": 33208}, {"template": "? calls ?", "facts": 16414}, {"template": "? imports ?", "facts": 6498}, {"template": "? raises ?", "facts": 4352}, {"template": "? inherits from ?", "facts": 4283}], "rules": [{"rule": "[? is defined in ?](a,b) & [? is `
- `egm_ask_many` `{"patterns": ["numpy___block_slicing is defined in ?", "cloudinit__read_seeded is defined in ?", "wheel__WheelFile_writestr is defined in ?"]}`
  - → 266 chars: `{"strict": true, "results": [{"pattern": "numpy___block_slicing is defined in ?", "strict": true, "values": []}, {"pattern": "cloudinit__read_seeded is defined in ?", "strict": true, "values": []}, {"pattern": "wheel__WheelFile_writestr is defined in ?", "strict": true, "values": []}]}`
- `egm_ask_many` `{"patterns": ["numpy___block_slicing is defined in ?", "cloudinit__read_seeded is defined in ?", "wheel__WheelFile_writestr is defined in ?", "? is defined in numpy", "? is defined in cloudinit", "? is defined in wheel"], "strict": false}`
  - → 524 chars: `{"strict": false, "results": [{"pattern": "numpy___block_slicing is defined in ?", "strict": false, "values": ["numpy___core__shape_base"]}, {"pattern": "cloudinit__read_seeded is defined in ?", "strict": false, "values": ["cloudinit__util"]}, {"pattern": "wheel__WheelFile_writestr is defined in ?",`
- `egm_ask` `{"pattern": "numpy___block_slicing is defined in ?", "strict": false}`
  - → 543 chars: `{"pattern": "numpy___block_slicing is defined in ?", "strict": false, "facts": [{"fact": "numpy___block_slicing is defined in numpy___core__shape_base", "subject": "numpy___block_slicing", "relation": "is defined in", "object": "numpy___core__shape_base", "status": "inferred", "tier": "tendency", "s`
- `egm_ask` `{"pattern": "cloudinit__read_seeded is defined in ?", "strict": false}`
  - → 504 chars: `{"pattern": "cloudinit__read_seeded is defined in ?", "strict": false, "facts": [{"fact": "cloudinit__read_seeded is defined in cloudinit__util", "subject": "cloudinit__read_seeded", "relation": "is defined in", "object": "cloudinit__util", "status": "inferred", "tier": "tendency", "score": 1, "beca`
- `egm_ask` `{"pattern": "wheel__WheelFile_writestr is defined in ?", "strict": false}`
  - → 533 chars: `{"pattern": "wheel__WheelFile_writestr is defined in ?", "strict": false, "facts": [{"fact": "wheel__WheelFile_writestr is defined in wheel__wheelfile", "subject": "wheel__WheelFile_writestr", "relation": "is defined in", "object": "wheel__wheelfile", "status": "inferred", "tier": "tendency", "score`

**Sonnet's answer**

I have all three answers, so here is the write-up. None of them is a stated fact. Each is a tendency-tier inference, so they are less certain than they might look.

| # | Symbol | Module | Status | Confidence |
|---|---|---|---|---|
| 1 | `numpy___block_slicing` | `numpy___core__shape_base` | Inferred (tendency) | Moderate |
| 2 | `cloudinit__read_seeded` | `cloudinit__util` | Inferred (tendency) | Moderate |
| 3 | `wheel__WheelFile_writestr` | `wheel__wheelfile` | Inferred (tendency) | Moderate |

**Evidence chains**

All three come from the same rule: if A calls B and B is defined in C, then A is defined in C. The knowledge base rates it as a tendency, with a hit rate of about 0.65.

1. `numpy___block_slicing` calls `numpy___block_info_recursion`, which is defined in `numpy___core__shape_base`.
2. `cloudinit__read_seeded` calls `cloudinit__load_yaml`, which is defined in `cloudinit__util`.
3. `wheel__WheelFile_writestr` calls `wheel__get_zipinfo_datetime`, which is defined in `wheel__wheelfile`.

**How I got there**

- With `strict=true`, the default that returns only stated facts and law-tier inferences, all three queries came back empty. The knowledge base has no stated "is defined in" fact for any of these symbols.
- With `strict=false`, each query returned one answer. In every case the note says "1 of 1 paths agree", but that means a single supporting path, not independent confirmation.

**Why only moderate confidence**

- The rule is right about 65% of the time, because a function often calls helpers from other modules.
- In each case the callee's module is the same one that plausibly holds the caller. The helpers look like same-file neighbours: `_block_slicing` and `_block_info_recursion` are both block-assembly helpers, and `writestr` and `get_zipinfo_datetime` both deal with zip handling.
- That is a plausibility argument from the names, not something the knowledge base proves.
- There is no corroborating path, such as an inheritance link or a second caller, and nothing contradicts the answers.

If you need certainty, check the source files directly. Treat these as strong hints, not confirmed facts.

**Checked against the hidden key and full facts**

| Claim | Verdict |
|---|---|
| numpy _block_slicing → numpy._core.shape_base | right (hidden fact, recovered by inference) |
| cloud-init read_seeded → cloudinit.util | right (hidden fact) |
| wheel WheelFile.writestr → wheel.wheelfile | right (hidden fact) |
| labelled all three inferred, tendency tier, moderate confidence | right: none was stated |

## 2. Impact analysis before a refactor

*Goal:* Impact analysis before a refactor: direct and second-level callers.  
*Knowledge base:* `code_realcode.txt`, settings `COVERAGE=0 MAXWORDS=42000`  
*Session:* claude-sonnet-5-5, 6 engine calls, 8 turns, 16.0 s, $0.09

**Prompt**

> I'm about to change the signature of cloud-init's load_yaml (cloudinit__load_yaml). Using only the egm tools, list every function that calls it directly, then every function that calls one of those callers. Group them by the module they are defined in where the knowledge base knows it, and flag anything you are unsure of.

**Tool calls** (results truncated)

- `egm_relations` `{}`
  - → 1,499 chars: `{"relations": [{"template": "? is defined in ?", "facts": 33208}, {"template": "? calls ?", "facts": 16414}, {"template": "? imports ?", "facts": 6498}, {"template": "? raises ?", "facts": 4352}, {"template": "? inherits from ?", "facts": 4283}], "rules": [{"rule": "[? is defined in ?](a,b) & [? is `
- `egm_ask` `{"pattern": "? calls cloudinit__load_yaml"}`
  - → 579 chars: `{"pattern": "? calls cloudinit__load_yaml", "strict": true, "facts": [{"fact": "cloudinit__read_conf calls cloudinit__load_yaml", "subject": "cloudinit__read_conf", "relation": "calls", "object": "cloudinit__load_yaml", "status": "stated"}, {"fact": "cloudinit__read_conf_from_cmdline calls cloudinit`
- `egm_ask_many` `{"patterns": ["? calls cloudinit__read_conf", "? calls cloudinit__read_conf_from_cmdline", "? calls cloudinit__read_seeded", "cloudinit__load_yaml is defined in ?", "cloudinit__read_conf is defined in ?", "cloudinit__read_conf_from_cmdline is defined in ?", "cloudinit__read_seeded is defined in ?"]}`
  - → 695 chars: `{"strict": true, "results": [{"pattern": "? calls cloudinit__read_conf", "strict": true, "values": ["cloudinit__read_conf_d", "cloudinit__read_conf_with_confd"]}, {"pattern": "? calls cloudinit__read_conf_from_cmdline", "strict": true, "values": []}, {"pattern": "? calls cloudinit__read_seeded", "st`
- `egm_ask_many` `{"patterns": ["cloudinit__read_conf_d is defined in ?", "cloudinit__read_conf_with_confd is defined in ?", "cloudinit__read_optional_seed is defined in ?"]}`
  - → 314 chars: `{"strict": true, "results": [{"pattern": "cloudinit__read_conf_d is defined in ?", "strict": true, "values": ["cloudinit__util"]}, {"pattern": "cloudinit__read_conf_with_confd is defined in ?", "strict": true, "values": []}, {"pattern": "cloudinit__read_optional_seed is defined in ?", "strict": true`
- `egm_ask_many` `{"patterns": ["cloudinit__load_yaml is defined in ?", "cloudinit__read_seeded is defined in ?", "? calls cloudinit__read_conf_from_cmdline"], "strict": false}`
  - → 303 chars: `{"strict": false, "results": [{"pattern": "cloudinit__load_yaml is defined in ?", "strict": false, "values": ["cloudinit__util"]}, {"pattern": "cloudinit__read_seeded is defined in ?", "strict": false, "values": ["cloudinit__util"]}, {"pattern": "? calls cloudinit__read_conf_from_cmdline", "strict":`
- `egm_ask` `{"pattern": "cloudinit__read_conf_with_confd is defined in ?", "strict": false}`
  - → 540 chars: `{"pattern": "cloudinit__read_conf_with_confd is defined in ?", "strict": false, "facts": [{"fact": "cloudinit__read_conf_with_confd is defined in cloudinit__util", "subject": "cloudinit__read_conf_with_confd", "relation": "is defined in", "object": "cloudinit__util", "status": "inferred", "tier": "t`

**Sonnet's answer**

Pulling the results together now. I've got everything I need from the knowledge base.

## Callers of `cloudinit__load_yaml`

**Direct callers (all stated facts):**

| Function | Module |
|---|---|
| `cloudinit__read_conf` | `cloudinit__util` (stated) |
| `cloudinit__read_conf_from_cmdline` | `cloudinit__util` (stated) |
| `cloudinit__read_seeded` | `cloudinit__util` (**inferred**, tendency tier) |

**Callers of those callers (second level):**

| Function | Calls | Module |
|---|---|---|
| `cloudinit__read_conf_d` | `read_conf` | `cloudinit__util` (stated) |
| `cloudinit__read_conf_with_confd` | `read_conf` | `cloudinit__util` (**inferred**, tendency tier; 2 of 2 paths agree) |
| `cloudinit__read_optional_seed` | `read_seeded` | `cloudinit__util` (stated) |
| *(none found)* | `read_conf_from_cmdline` | n/a |

## What I'm unsure of

- **Module for `read_seeded` and `read_conf_with_confd`:** the knowledge base has no stated definition for either. The `cloudinit__util` placement comes from a tendency-tier rule: "calls X, and X is defined in M, so the caller is defined in M". That rule holds about 65% of the time. Check both by hand.
- **Module of `load_yaml` itself:** only an inferred `cloudinit__util`, not a stated one.
- **Callers only:** the knowledge base records `calls` edges. It won't show dynamic dispatch, calls through aliases or re-exports, or callers outside the indexed code. Tests, plugins and anything that imports `load_yaml` under another name could be missing.
- **`read_conf_from_cmdline` has no callers:** the strict and non-strict queries both return none. That could mean it's unused, or it could be called in a way the index missed. I'd grep for it before concluding it's dead code.
- **Depth:** I stopped at two levels, as you asked. Callers of `read_conf_d`, `read_conf_with_confd` and `read_optional_seed` would be the next ring if the signature change propagates.

**Checked against the hidden key and full facts**

| Claim | Verdict |
|---|---|
| 3 direct callers | right: 3 of 3, none missed |
| 3 second-level callers | right: 3 of 3, none missed |
| modules of the 6 callers | right: 6 of 6, two of them inferred from hidden facts and flagged as such |
| read_conf_from_cmdline has no callers | right in the full facts; it suggested grepping before calling it dead code |

## 3. Debugging: where can this exception come from?

*Goal:* Debugging: trace an exception to where it can be raised.  
*Knowledge base:* `code_realcode.txt`, settings `COVERAGE=0 MAXWORDS=42000`  
*Session:* claude-sonnet-5-5, 5 engine calls, 7 turns, 19.0 s, $0.11

**Prompt**

> A cloud-init run crashed with ProcessExecutionError (cloudinit__ProcessExecutionError). Using only the egm tools, find which functions or modules can raise it, where those are defined, and which other functions call them, so I know where to start debugging. Separate what the knowledge base states from what it infers.

**Tool calls** (results truncated)

- `egm_relations` `{}`
  - → 1,499 chars: `{"relations": [{"template": "? is defined in ?", "facts": 33208}, {"template": "? calls ?", "facts": 16414}, {"template": "? imports ?", "facts": 6498}, {"template": "? raises ?", "facts": 4352}, {"template": "? inherits from ?", "facts": 4283}], "rules": [{"rule": "[? is defined in ?](a,b) & [? is `
- `egm_ask` `{"pattern": "? raises cloudinit__ProcessExecutionError"}`
  - → 4,631 chars: `{"pattern":"? raises cloudinit__ProcessExecutionError","strict":true,"facts":[{"fact":"cloudinit__find_home raises cloudinit__ProcessExecutionError","subject":"cloudinit__find_home","relation":"raises","object":"cloudinit__ProcessExecutionError","status":"stated"},{"fact":"cloudinit__subp raises clo`
- `egm_ask_many` `{"patterns": ["cloudinit__find_home is defined in ?", "cloudinit__subp is defined in ?", "? calls cloudinit__find_home", "? calls cloudinit__subp", "? calls cloudinit__which", "? calls cloudinit__prepend_base_command", "? calls cloudinit__raise_on_invalid_command", "? calls cloudinit__is_exe", "? raises cloudinit__ProcessExecutionError", "? inherits from cloudinit__ProcessExecutionError"], "strict …`
  - → 1,305 chars: `{"strict": false, "results": [{"pattern": "cloudinit__find_home is defined in ?", "strict": false, "values": ["cloudinit__sources__DataSourceWSL"]}, {"pattern": "cloudinit__subp is defined in ?", "strict": false, "values": ["cloudinit__subp"]}, {"pattern": "? calls cloudinit__find_home", "strict": f`
- `egm_ask_many` `{"patterns": ["cloudinit__runparts is defined in ?", "cloudinit__prepend_base_command is defined in ?", "cloudinit__which is defined in ?", "cloudinit__raise_on_invalid_command is defined in ?", "cloudinit__is_exe is defined in ?", "? calls cloudinit__runparts", "? calls cloudinit__run_commands", "cloudinit__ProcessExecutionError is defined in ?", "cloudinit__runparts raises ?"], "strict": false}`
  - → 886 chars: `{"strict": false, "results": [{"pattern": "cloudinit__runparts is defined in ?", "strict": false, "values": ["cloudinit__subp"]}, {"pattern": "cloudinit__prepend_base_command is defined in ?", "strict": false, "values": ["cloudinit__subp"]}, {"pattern": "cloudinit__which is defined in ?", "strict": `
- `egm_history` `{"pattern": "? raises cloudinit__ProcessExecutionError"}`
  - → 68 chars: `{"pattern": "? raises cloudinit__ProcessExecutionError", "history": []}`

**Sonnet's answer**

I've finished querying the knowledge base, so here is the write-up.

## Where `cloudinit__ProcessExecutionError` comes from

**Stated by the knowledge base**
- `cloudinit__subp` raises it. This is the main source. The `subp` module is also where the exception class is defined (`cloudinit__ProcessExecutionError is defined in cloudinit__subp`).
- `cloudinit__find_home` raises it directly. It is defined in `cloudinit__sources__DataSourceWSL`, so it only matters on WSL.

**Inferred (law tier, score 0.83)**
The rule is "defined in module M, and M raises X, so the item raises X". It marks these as raising the error only because they sit in the `subp` module:
- `cloudinit__which`
- `cloudinit__is_exe`
- `cloudinit__prepend_base_command`
- `cloudinit__raise_on_invalid_command`
- `cloudinit__ProcessExecutionError___init__`
- `cloudinit__ProcessExecutionError__ensure_string`

These are weak leads. The rule only says the module raises the error, not that each function does.

**Inferred (tendency tier, only shown with `strict=false`)**
- `cloudinit__runparts` is defined in `cloudinit__subp`. The knowledge base also says it raises `TypeError` and this error.

## Callers

**Stated or inferred by the knowledge base**
- `cloudinit__subp` is called by:
  - `cloudinit___write_command_output_to_file`
  - `cloudinit__collect_logs`
  - `cloudinit__handle_clean_args`
  - `cloudinit__runparts`
- `cloudinit__find_home` is called by `cloudinit__DataSourceWSL__get_data`.
- `cloudinit__prepend_base_command` is called by `cloudinit__run_commands`.
- `cloudinit__which` calls `cloudinit__is_exe`.

**No callers recorded**
- `which`, `raise_on_invalid_command`, `runparts` and `run_commands` have no recorded callers.
- I did not find `runparts` or `run_commands` called from anywhere. That means the call graph is incomplete here, not that nothing calls them.

## My reading

This part is my inference, not the knowledge base's.
- Most `ProcessExecutionError` crashes in cloud-init come from `subp`, which wraps a subprocess that exited non-zero. Look at the exception's command, exit code, stdout and stderr in the crash log first.
- The traceback will name the calling frame. It should be one of the four `subp` callers above, or something outside what the knowledge base recorded.
- If the run was on WSL, check `DataSourceWSL__get_data` and `find_home` first.
- If the traceback goes through `run_commands`, look at `prepend_base_command`.

## Caveats
- `egm_history` shows no earlier values, so none of these facts were revised.
- The knowledge base only has direct `raises` facts for `subp` and `find_home`. Because it only records direct calls, it cannot tell you the full chain from a cloud-init stage down to `subp`.
- I didn't run `egm_conflicts`, so I haven't checked whether any of these facts are disputed.

**Checked against the hidden key and full facts**

| Claim | Verdict |
|---|---|
| subp and find_home raise it (stated) | right |
| 4 callers of subp | right: 4 of 4 |
| 7 functions inferred to raise it because they sit in the subp module | 1 of 7 right (raise_on_invalid_command, a hidden fact); Sonnet called these "weak leads". The rule rests on a name collision in the extractor (section below) |
| missed create_swapfile (hidden, in another module) | no path in the facts could reach it |

## 4. Debugging the knowledge itself: a million suspicious facts

*Goal:* Debugging the knowledge itself: why does the dpkg knowledge base derive over a million facts?  
*Knowledge base:* `world_packages.txt`, settings `defaults`  
*Session:* claude-sonnet-5-5, 22 engine calls, 24 turns, 100.4 s, $0.18

**Prompt**

> This egm knowledge base holds about 14,000 facts about installed Debian packages (depends on, recommends, section, priority, architecture, source). Inference derives over a million 'depends on' facts from them. Using only the egm tools, investigate whether the derived dependencies can be trusted and what causes the volume. Name the specific rules responsible, with their evidence, and recommend what to change.

**Tool calls** (results truncated)

- `egm_relations` `{"include_rejected": true}`
  - → 3,303 chars: `{"relations":[{"template":"? depends on ?","facts":6389},{"template":"? is in section ?","facts":1638},{"template":"? has priority ?","facts":1631},{"template":"? is for architecture ?","facts":1627},{"template":"? provides ?","facts":1460},{"template":"? is built from ?","facts":1062},{"template":"`
- `egm_conflicts` `{}`
  - → 1,375 chars: `Error: result (75,063 characters) exceeds maximum allowed tokens. Output was saved to a file. file>
Format: JSON with schema: {conflicts: [{...}]}
- For targeted queries (find a value, filter by field): use jq on the file directly.
- For analysis or summarization that requires reading the full conte`
- `egm_infer` `{"relation": "depends on", "limit": 25}`
- `egm_history` `{"pattern": "? depends on ?"}`
  - → 1,578 chars: `{"total": 1150230, "facts": [{"fact": "pkg_3cpio depends on pkg_accountsservice", "tier": "law"}, {"fact": "pkg_3cpio depends on pkg_default_dbus_system_bus", "tier": "law"}, {"fact": "pkg_3cpio depends on pkg_libpolkit_gobject_1_0", "tier": "law"}, {"fact": "pkg_3cpio depends on pkg_polkitd", "tier`
- `egm_ask` `{"pattern": "pkg_3cpio depends on ?"}`
- `egm_ask` `{"pattern": "pkg_3cpio recommends ?"}`
  - → 99 chars: `{"pattern": "pkg_3cpio recommends ?", "strict": true, "facts": [], "note": "no stated or inferred answer"}`
- `egm_ask` `{"pattern": "pkg_3cpio depends on pkg_accountsservice"}`
  - → 652 chars: `{"pattern": "pkg_3cpio depends on pkg_accountsservice", "strict": true, "facts": [{"fact": "pkg_3cpio depends on pkg_accountsservice", "subject": "pkg_3cpio", "relation": "depends on", "object": "pkg_accountsservice", "status": "inferred", "tier": "law", "score": 0, "because": ["pkg_3cpio depends on`
- `egm_ask` `{"pattern": "? recommends pkg_accountsservice"}`
  - → 109 chars: `{"pattern": "? recommends pkg_accountsservice", "strict": true, "facts": [], "note": "no stated or inferred answer"}`
- `egm_ask` `{"pattern": "pkg_accountsservice depends on ?"}`
  - → 1,418 chars: `Error: result (595,332 characters) exceeds maximum allowed tokens. Output was saved to a file. file>
Format: JSON with schema: {pattern: string, strict: boolean, facts: [{...}]}
- For targeted queries (find a value, filter by field): use jq on the file directly.
- For analysis or summarization that `
- `egm_ask_many` `{"patterns": ["pkg_3cpio depends on pkg_systemd_resolved", "pkg_systemd_resolved depends on pkg_accountsservice", "pkg_3cpio depends on pkg_libc6", "pkg_systemd_resolved depends on pkg_libc6", "pkg_accountsservice depends on pkg_systemd_resolved"]}`
- `egm_ask` `{"pattern": "pkg_3cpio depends on pkg_systemd_resolved", "strict": true}`
  - → 533 chars: `{"strict": true, "results": [{"pattern": "pkg_3cpio depends on pkg_systemd_resolved", "strict": true, "values": ["pkg_3cpio"]}, {"pattern": "pkg_systemd_resolved depends on pkg_accountsservice", "strict": true, "values": ["pkg_systemd_resolved"]}, {"pattern": "pkg_3cpio depends on pkg_libc6", "stric`
- `egm_ask_many` `{"patterns": ["pkg_libc6 depends on pkg_systemd_resolved", "pkg_libc6 depends on pkg_libgcc_s1", "pkg_libgcc_s1 depends on pkg_libc6", "pkg_systemd_resolved depends on pkg_libc6", "pkg_libc6 depends on pkg_libc6", "pkg_libc6 recommends ?", "? recommends pkg_libc6", "pkg_systemd_resolved recommends ?"]}`
  - → 701 chars: `{"strict": true, "results": [{"pattern": "pkg_libc6 depends on pkg_systemd_resolved", "strict": true, "values": ["pkg_libc6"]}, {"pattern": "pkg_libc6 depends on pkg_libgcc_s1", "strict": true, "values": ["pkg_libc6"]}, {"pattern": "pkg_libgcc_s1 depends on pkg_libc6", "strict": true, "values": ["pk`
- `egm_ask` `{"pattern": "pkg_libc6 depends on pkg_systemd_resolved"}`
  - → 632 chars: `{"pattern": "pkg_libc6 depends on pkg_systemd_resolved", "strict": true, "facts": [{"fact": "pkg_libc6 depends on pkg_systemd_resolved", "subject": "pkg_libc6", "relation": "depends on", "object": "pkg_systemd_resolved", "status": "inferred", "tier": "law", "score": 0.03, "because": ["pkg_libc6 reco`
- `egm_ask` `{"pattern": "pkg_libc6 depends on pkg_libgcc_s1"}`
  - → 625 chars: `{"pattern": "pkg_libc6 depends on pkg_libgcc_s1", "strict": true, "facts": [{"fact": "pkg_libc6 depends on pkg_libgcc_s1", "subject": "pkg_libc6", "relation": "depends on", "object": "pkg_libgcc_s1", "status": "inferred", "tier": "law", "score": 0.01, "because": ["pkg_libc6 depends on pkg_systemd_re`
- `egm_ask` `{"pattern": "pkg_libgcc_s1 depends on pkg_libc6"}`
  - → 207 chars: `{"pattern": "pkg_libgcc_s1 depends on pkg_libc6", "strict": true, "facts": [{"fact": "pkg_libgcc_s1 depends on pkg_libc6", "subject": "pkg_libgcc_s1", "relation": "depends on", "object": "pkg_libc6", "status": "stated"}]}`
- `egm_ask` `{"pattern": "pkg_libidn2_0 depends on pkg_systemd_resolved"}`
  - → 522 chars: `{"pattern": "pkg_libidn2_0 depends on pkg_systemd_resolved", "strict": true, "facts": [{"fact": "pkg_libidn2_0 depends on pkg_systemd_resolved", "subject": "pkg_libidn2_0", "relation": "depends on", "object": "pkg_systemd_resolved", "status": "inferred", "tier": "law", "score": 0.12, "because": ["pk`
- `egm_ask` `{"pattern": "pkg_libidn2_0 depends on pkg_libc6"}`
  - → 207 chars: `{"pattern": "pkg_libidn2_0 depends on pkg_libc6", "strict": true, "facts": [{"fact": "pkg_libidn2_0 depends on pkg_libc6", "subject": "pkg_libidn2_0", "relation": "depends on", "object": "pkg_libc6", "status": "stated"}]}`
- `egm_ask` `{"pattern": "pkg_systemd_resolved depends on pkg_libidn2_0"}`
  - → 708 chars: `{"pattern": "pkg_systemd_resolved depends on pkg_libidn2_0", "strict": true, "facts": [{"fact": "pkg_systemd_resolved depends on pkg_libidn2_0", "subject": "pkg_systemd_resolved", "relation": "depends on", "object": "pkg_libidn2_0", "status": "inferred", "tier": "law", "score": 0.01, "because": ["pk`
- `egm_ask` `{"pattern": "? recommends pkg_libidn2_0"}`
  - → 356 chars: `{"pattern": "? recommends pkg_libidn2_0", "strict": true, "facts": [{"fact": "pkg_libc6 recommends pkg_libidn2_0", "subject": "pkg_libc6", "relation": "recommends", "object": "pkg_libidn2_0", "status": "stated"}, {"fact": "pkg_systemd_resolved recommends pkg_libidn2_0", "subject": "pkg_systemd_resol`
- `egm_ask` `{"pattern": "pkg_systemd_resolved depends on pkg_accountsservice"}`
  - → 666 chars: `{"pattern": "pkg_systemd_resolved depends on pkg_accountsservice", "strict": true, "facts": [{"fact": "pkg_systemd_resolved depends on pkg_accountsservice", "subject": "pkg_systemd_resolved", "relation": "depends on", "object": "pkg_accountsservice", "status": "inferred", "tier": "law", "score": 0.0`
- `egm_ask` `{"pattern": "pkg_default_dbus_system_bus depends on pkg_libidn2_0"}`
  - → 671 chars: `{"pattern": "pkg_default_dbus_system_bus depends on pkg_libidn2_0", "strict": true, "facts": [{"fact": "pkg_default_dbus_system_bus depends on pkg_libidn2_0", "subject": "pkg_default_dbus_system_bus", "relation": "depends on", "object": "pkg_libidn2_0", "status": "inferred", "tier": "law", "score": `
- `egm_ask` `{"pattern": "pkg_libidn2_0 depends on pkg_default_dbus_system_bus"}`
  - → 715 chars: `{"pattern": "pkg_libidn2_0 depends on pkg_default_dbus_system_bus", "strict": true, "facts": [{"fact": "pkg_libidn2_0 depends on pkg_default_dbus_system_bus", "subject": "pkg_libidn2_0", "relation": "depends on", "object": "pkg_default_dbus_system_bus", "status": "inferred", "tier": "law", "score": `

**Sonnet's answer**

I have enough evidence to answer, so I'm writing it up now. The derived dependencies can't be trusted. Of the 1,150,230 inferred "depends on" facts, nearly all come from a cycle that two rules create together.

## Verdict

The proofs for these inferences are all well-formed, but many of them are false. For example, `pkg_3cpio depends on pkg_accountsservice` is derived at law tier, and a small archive tool has no such dependency. Everything with a dependency path to libc6 ends up depending on everything else in the same cycle.

## The rules responsible

All of these are accepted "law" rules from `egm_relations`.

**1. `recommends(a,b) ⇒ depends on(b,a)` (inverse, law, rate 0.12, 59 of 489 conclusions stated).**
- This is the root cause. It reverses the direction of a "recommends" fact, and it turns a weak relation into a hard one.
- Evidence: the stated fact `pkg_systemd_resolved recommends pkg_libidn2_0` produces `pkg_libidn2_0 depends on pkg_systemd_resolved`.
- It is wrong about 88% of the time, yet it is classed as a law. The rate was low and the lift (51.9) was high, so lift appears to have been enough to promote it.

**2. `recommends(a,b) & depends on(b,c) ⇒ depends on(a,c)` (law, rate 0.20, 461 of 2,344 chains stated).**
- This treats an optional recommendation as if it were a hard dependency, and it is wrong about 80% of the time.
- Evidence: `pkg_libc6 recommends pkg_libidn2_0` is stated, and libidn2 has an inferred dependency on systemd-resolved (rule 1). Together they give `pkg_libc6 depends on pkg_systemd_resolved`.

**3. `depends on(a,b) & depends on(b,c) ⇒ depends on(a,c)` (transitivity, law, rate 0.27, 16,723 chains seen).**
- Transitivity is sound for genuine dependencies. Here it runs over the outputs of rules 1 and 2, and over their cycles, so it multiplies the errors.
- Chain 1: `3cpio → libc6` (stated), then `libc6 → systemd_resolved` (rule 2), gives `3cpio → systemd_resolved`.
- Chain 2: `systemd_resolved → fwupd → accountsservice` gives `systemd_resolved → accountsservice`.
- Chain 3: combining those gives `3cpio → accountsservice`.
- The same mechanism produced `libc6 depends on libgcc_s1`. The stated direction is the opposite: `libgcc_s1 depends on libc6`.
- Cycles also appear, such as `libidn2_0 → default_dbus_system_bus` while `default_dbus_system_bus → libidn2_0`. Real Debian dependency chains don't loop like this.

## Why the volume is so large

The mechanism, in order:
1. libc6 is depended on by almost every package, and it stated-recommends `libidn2_0`.
2. Rule 1 gives `libidn2_0` a dependency on `systemd_resolved` and on other packages that recommend it.
3. Rule 2 feeds that back to libc6 and to everything that depends on libc6.
4. Rule 3 closes the whole cycle, so every package in it ends up depending on every other.

The result is 1,150,230 inferred facts from 6,389 stated ones (about 180 times). Per-package fan-out is huge, and `pkg_3cpio` alone has hundreds of inferred dependencies.

## What I did not check

- I traced individual proofs only for libc6, libidn2, systemd-resolved, fwupd, accountsservice and dbus.
- I did not measure how many of the million facts sit inside the cycle versus outside it.
- `egm_conflicts` returned 75k characters and I didn't analyse it, because reading that saved file would have needed tools outside egm.
- `egm_history` returned nothing for "depends on", so no stated facts have been corrected or withdrawn.

## Recommendations

1. **Remove rule 1** (`recommends ⇒ depends on` inverse). It is semantically backwards, and a 12% hit rate should never qualify as a law.
2. **Remove or demote rule 2** (recommends then depends on). Its 20% rate fits the tendency tier at best. Keep it out of strict answers.
3. **Make "recommends" and "depends on" separate relations in rule premises.** Weak edges shouldn't feed rules whose conclusion is a hard dependency. The rejected rules `depends on & recommends ⇒ depends on` (rate 0.02) and `recommends & recommends ⇒ depends on` (rate 0.04) already show that the system treats such rules as bad.
4. **Gate the law tier on rate, not lift alone.** Require a minimum rate, for example above 0.9, because lift is inflated when the base rate is tiny. The transitivity rule at 0.27 is also questionable as a law, so consider a depth limit or restricting it to stated edges only.
5. **Keep transitivity, but only over stated "depends on" edges.** That gives a real transitive closure, which is useful for questions like "what does X pull in". Expect it to be large but defensible.
6. **After the change, re-run `egm_relations` and `egm_infer`.** The "depends on" inference count should drop sharply, and spot-checks such as `3cpio → accountsservice` and `libc6 → libgcc_s1` should no longer appear.

Until those rules are fixed, treat inferred "depends on" facts as unreliable. Only the stated facts and the transitive facts built purely from stated edges are safe to use.

**Checked against the hidden key and full facts**

| Claim | Verdict |
|---|---|
| root cause: recommends(a,b) ⇒ depends on(b,a), law tier at 12% agreement | right: the same finding as the full-truth analysis in the stress report |
| 3cpio → accountsservice, libc6 → systemd-resolved, libidn2 ↔ dbus are false | right: none is in the real transitive closure |
| "libc6 depends on libgcc-s1 is backwards" | wrong: Debian's libc6 does depend on libgcc-s1. It was a hidden fact the engine recovered correctly |
| "real Debian dependency chains don't loop" | wrong: libc6 and libgcc-s1 depend on each other |
| three tool results were too large for the client (75k-595k characters) | an MCP server gap: egm_conflicts and egm_ask have no size limit |

## How to run your own

```
egm mcp facts.txt --set MAXWORDS=50000      # size MAXWORDS to the vocabulary first
claude mcp add egm -- egm mcp /abs/path/facts.txt
```

Then ask in plain language. Ask the model to separate stated from inferred facts and to show the proof; the tools return both.
