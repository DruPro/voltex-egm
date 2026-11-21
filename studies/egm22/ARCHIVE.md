# Voltex v2.2 (EGM) validation, and LLM vs EGM

Archived from the working folder `/home/claude/work/egm22` as it was when the study ended. Paper: `docs/papers/Evidence Before Inference Source-Aware Observation Enrichment for Evolving Knowl.pdf`.

Nothing was edited. Raw logs and agent audit logs are included as they were written.

## Packed folders

Unpack with `tar -xJf <file>` in this folder.

| Folder | Archive | Size | Packed |
|---|---|---|---|
| `data/` | `data.tar.xz` | 72.7 MB | 1.7 MB |
| `llm_out/` | `llm_out.tar.xz` | 2.0 MB | 0.1 MB |
| `logs/` | `logs.tar.xz` | 232.0 MB | 3.2 MB |

## Binaries left out

Built from the `.cpp` files in this folder (or `src/voltex2.cpp`). sha256 of the copies used:

- `voltex2` 0ca4e11906d8dc871e8a102e3319edd049d23ef0336df80b95b5ea0edac5840e

## Absolute paths

These files name paths under `/home/claude/`, where the study ran. Adjust them (or recreate that layout) to rerun:

- `exp_v22.py`
- `gate.sh`
- `gen_llm.py`
- `score_llm.py`
- `v5_refresh.py`
