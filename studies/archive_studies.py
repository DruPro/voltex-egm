#!/usr/bin/env python3
"""Copy the earlier studies from the work area into the repo's studies/ folder, for transparency.

Kept: pre-registrations, generators, harnesses, scorers, hidden answer keys, inputs, raw answers,
agent audit logs, results. Large log/data folders (> 2 MB) are stored as one .tar.xz each.
Left out, and listed in each study's ARCHIVE.md: compiled binaries (sha256 recorded), downloaded
third-party source (name and version recorded), Python caches and self-test save files.
"""
import hashlib, os, shutil, subprocess, sys, json

WORK = "/home/claude/work"
REPO = sys.argv[1] if len(sys.argv) > 1 else "/home/claude/drupro/voltex-egm"
STUDIES = {  # source dir -> (repo name, title, paper)
    "_v1": ("v1_audit", "Audit of Voltex v1: what the code actually computes", "Voltex Research & Architectural Assessment.pdf"),
    "v21": ("v21_baseline", "Frozen Voltex v2.1 baseline and its gates", "Voltex Research & Architectural Assessment.pdf"),
    "v2": ("v2_containment", "Voltex v2: rule discovery, PCA agreement, benchmarks", "Evidential Grammar Memory A Rule-Discovering, Self-Correcting Memory Tool for La.pdf"),
    "improve": ("improve", "Improvement experiments: tiers, retraction, refresh, scoring", "Voltex Improvement Experiments Findings and Decisions.pdf"),
    "blind": ("blind_world", "Blind world discovery", "Voltex Blind World Discovery Results.pdf"),
    "amend": ("amend", "AMEND: amendments as operations", "Amendments in Voltex an experiment.pdf"),
    "declarative": ("declarative", "Declarative amendments through evidence ingestion", "Declarative amendments in Voltex can a change be knowledge instead of an operati.pdf"),
    "evolve": ("evolve", "Dynamic relational evolution: where should change live", "Dynamic relational evolution in Voltex where should change live.pdf"),
    "egm22": ("egm22", "Voltex v2.2 (EGM) validation, and LLM vs EGM", "Evidence Before Inference Source-Aware Observation Enrichment for Evolving Knowl.pdf"),
    "realcode": ("realcode", "Real codebase: LLM-extracted facts plus EGM retrieval", "Extract Once, Query Forever LLM-Extracted Codebase Facts in Evidential Grammar M.pdf"),
    "scale_econ": ("tokenomics", "Tokenomics of programmatic distillation", "Tokenomics of Programmatic Distillation EGM Keeps an LLM's Query Cost Flat as Kn.pdf"),
    "code": ("code_facts", "Standard-library code facts graded by an AST parser", "Extract Once, Query Forever LLM-Extracted Codebase Facts in Evidential Grammar M.pdf"),
    "complex": ("company", "Company world: clean and noisy (15%, 30%) data", "Evidential Grammar Memory A Rule-Discovering, Self-Correcting Memory Tool for La.pdf"),
    "agentlab": ("agentlab", "Agent lab: Haiku and Sonnet with search vs with Voltex", "Tokenomics of Programmatic Distillation EGM Keeps an LLM's Query Cost Flat as Kn.pdf"),
    "explain": ("explain_apples", "Explanations and the 'are apples blue?' demonstration", "docs/THEORY.md"),
    "math": ("math", "Mathematics by example: divisibility and remainders", "docs/THEORY.md"),
    "pbe": ("programming_by_example", "Programming inference by example", "docs/THEORY.md"),
    "demo": ("demo", "Demonstration session used in the posts", "media/"),
}
V1_FILES = ["exp1_structure.py", "exp2_counters.py", "exp3_mdl.py", "results_e1_e4.json", "results_e5_e7.json",
            "results_e8.json", "voltex_linux.cpp", "vtx.py"]
THIRD_PARTY_DIRS = {"src_dl", "pkg_download"}
THIRD_PARTY_FILES = {"code/data/raw_lines.txt": "lines of the typeshed stdlib stubs bundled with mypy 2.3.1 (regenerate with code/extract.py)"}
PACK_DIRS = ("logs", "data", "obs", "hidden", "llm_out", "llm", "llm_hidden", "results")
PACK_LIMIT = 2_000_000


def is_elf(p):
    with open(p, "rb") as f:
        return f.read(4) == b"\x7fELF"


def size(p):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def archive(src_root, entries, dest, rel_prefix, notes):
    for name in entries:
        s = os.path.join(src_root, name); d = os.path.join(dest, name); rel = f"{rel_prefix}/{name}"
        if name == "__pycache__" or name.endswith((".pyc", ".tar.gz", ".zip")) and os.path.isfile(s) and "src_dl" in rel:
            continue
        if os.path.isdir(s):
            if name in THIRD_PARTY_DIRS:
                notes["third_party"] += [f"`{rel}/{x}`" for x in sorted(os.listdir(s)) if not x.endswith(".tar.gz")]
                continue
            if name.startswith(PACK_DIRS) and size(s) > PACK_LIMIT:
                cleaned = [x for x in sorted(os.listdir(s)) if x != "__pycache__"]
                elfs = [x for x in cleaned if os.path.isfile(os.path.join(s, x)) and is_elf(os.path.join(s, x))]
                for x in elfs:
                    notes["binaries"].append((f"{rel}/{x}", sha(os.path.join(s, x))))
                tp = [k for k in THIRD_PARTY_FILES if k.startswith(f"{notes['src']}/{rel.lstrip('/')}/")]
                for k in tp:
                    notes["third_party"].append(f"`{k.split('/', 1)[1]}`: {THIRD_PARTY_FILES[k]}")
                elfs += [k.split("/", 1)[1][len(rel.lstrip('/')) - len(name):][len(name) + 1:] for k in tp]
                tarp = d + ".tar.xz"
                subprocess.run(["tar", "-C", src_root, "--exclude=__pycache__", *[f"--exclude={name}/{x}" for x in elfs],
                                "-cJf", tarp, name], check=True, env={**os.environ, "XZ_OPT": "-6 -T0"})
                notes["packed"].append((f"{rel}/", f"{rel}.tar.xz", size(s), os.path.getsize(tarp)))
                continue
            os.makedirs(d, exist_ok=True)
            archive(s, sorted(os.listdir(s)), d, rel, notes)
            continue
        if name.endswith(".tar.gz") and rel.split("/")[-2] in THIRD_PARTY_DIRS:
            continue
        key = rel.split("/", 1)[1] if "/" in rel else rel
        if f"{notes['src']}/{key}" in THIRD_PARTY_FILES:
            notes["third_party"].append(f"`{rel}`: {THIRD_PARTY_FILES[notes['src'] + '/' + key]}")
            continue
        if name.endswith(".pyc"):
            continue
        if is_elf(s):
            notes["binaries"].append((rel, sha(s))); continue
        if name == "selftest.vtx2":
            continue
        shutil.copy2(s, d)
        with open(s, "rb") as f:
            if b"/home/claude/" in f.read():
                notes["abs_paths"].append(rel)


def main():
    index = []
    for src, (name, title, paper) in STUDIES.items():
        dest = os.path.join(REPO, "studies", name)
        if os.path.exists(dest):
            sys.exit(f"{dest} exists; archive into a fresh clone")
        os.makedirs(dest)
        notes = {"src": src, "binaries": [], "third_party": [], "packed": [], "abs_paths": []}
        if src == "_v1":
            archive(WORK, V1_FILES, dest, "", notes)
        else:
            archive(os.path.join(WORK, src), sorted(os.listdir(os.path.join(WORK, src))), dest, "", notes)
        files = sum(len(fs) for _, _, fs in os.walk(dest))
        with open(os.path.join(dest, "ARCHIVE.md"), "w") as f:
            f.write(f"# {title}\n\nArchived from the working folder `{WORK}/{src if src != '_v1' else ''}` "
                    f"as it was when the study ended. Paper: `{paper if '/' in paper else 'docs/papers/' + paper}`.\n\n"
                    "Nothing was edited. Raw logs and agent audit logs are included as they were written.\n")
            if notes["packed"]:
                f.write("\n## Packed folders\n\nUnpack with `tar -xJf <file>` in this folder.\n\n| Folder | Archive | Size | Packed |\n|---|---|---|---|\n")
                for a, b, x, y in notes["packed"]:
                    f.write(f"| `{a.lstrip('/')}` | `{b.lstrip('/')}` | {x/1e6:.1f} MB | {y/1e6:.1f} MB |\n")
            if notes["binaries"]:
                f.write("\n## Binaries left out\n\nBuilt from the `.cpp` files in this folder (or `src/voltex2.cpp`). sha256 of the copies used:\n\n")
                for p, h in notes["binaries"]:
                    f.write(f"- `{p.lstrip('/')}` {h}\n")
            if notes["third_party"]:
                f.write("\n## Third-party material left out\n\nOther projects' code, not ours to redistribute here. Fetch the same versions (PyPI) to rerun.\n\n")
                for p in notes["third_party"]:
                    f.write(f"- {p.replace('`/', '`')}\n")
            if notes["abs_paths"]:
                f.write(f"\n## Absolute paths\n\nThese files name paths under `/home/claude/`, where the study ran. "
                        "Adjust them (or recreate that layout) to rerun:\n\n")
                for p in notes["abs_paths"]:
                    f.write(f"- `{p.lstrip('/')}`\n")
        index.append((name, title, paper, files, size(dest)))
        print(f"{name:24s} {files:5d} files {size(dest)/1e6:6.1f} MB  bins={len(notes['binaries'])} packed={len(notes['packed'])}")
    json.dump(index, open("/tmp/archive_index.json", "w"), indent=1)


if __name__ == "__main__":
    main()
