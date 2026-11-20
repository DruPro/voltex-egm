# Agent lab: Haiku and Sonnet with search vs with Voltex

Archived from the working folder `/home/claude/work/agentlab` as it was when the study ended. Paper: `docs/papers/Tokenomics of Programmatic Distillation EGM Keeps an LLM's Query Cost Flat as Kn.pdf`.

Nothing was edited. Raw logs and agent audit logs are included as they were written.

## Binaries left out

Built from the `.cpp` files in this folder (or `src/voltex2.cpp`). sha256 of the copies used:

- `env_haiku_voltex/.engine/voltex2` eb1a1c57f7f9b5b965de9007c85e38e14900fe9aa6cc24fa4a46b4aa11289d43
- `env_scripted_voltex/.engine/voltex2` eb1a1c57f7f9b5b965de9007c85e38e14900fe9aa6cc24fa4a46b4aa11289d43
- `env_sonnet_voltex/.engine/voltex2` eb1a1c57f7f9b5b965de9007c85e38e14900fe9aa6cc24fa4a46b4aa11289d43
- `r2_haiku_voltex/.engine/voltex2` eb1a1c57f7f9b5b965de9007c85e38e14900fe9aa6cc24fa4a46b4aa11289d43
- `r2_scripted_voltex/.engine/voltex2` eb1a1c57f7f9b5b965de9007c85e38e14900fe9aa6cc24fa4a46b4aa11289d43
- `r2_sonnet_voltex/.engine/voltex2` eb1a1c57f7f9b5b965de9007c85e38e14900fe9aa6cc24fa4a46b4aa11289d43

## Absolute paths

These files name paths under `/home/claude/`, where the study ran. Adjust them (or recreate that layout) to rerun:

- `build_lab.py`
- `build_round2.py`
- `prompt_haiku_search.txt`
- `prompt_haiku_voltex.txt`
- `prompt_r2_haiku_search.txt`
- `prompt_r2_haiku_voltex.txt`
- `prompt_r2_sonnet_search.txt`
- `prompt_r2_sonnet_voltex.txt`
- `prompt_sonnet_search.txt`
- `prompt_sonnet_voltex.txt`
- `score.py`
- `score_r2.py`
- `scripted_voltex.py`
- `scripted_voltex_r2.py`
