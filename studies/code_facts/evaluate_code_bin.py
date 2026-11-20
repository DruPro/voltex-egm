"""Score Voltex's inferred return types against the official stubs."""
import json, subprocess, collections, os
t = json.load(open("data/code_truth.json"))
truth = t["returns"]; hidden = set(t["hidden"])
extra = os.environ.get("EXTRA", "")
out = subprocess.run([os.environ.get("BIN", "../v2/voltex2")], input=f"INGESTFILE data/code_facts.txt\n{extra}RELATIONS\nINFER ALL\nCONFLICTS\nEXIT\n",
                     capture_output=True, text=True).stdout
open("data/run.log", "w").write(out)
print("\n".join(l for l in out.splitlines() if l.startswith(("[INGEST]", "[RELATIONS]", "  #")) or l.strip().startswith(("ACCEPT", "reject"))))
derived = collections.defaultdict(list)
for l in out.splitlines():
    if l.startswith("FACT\t"):
        f = l.split("\t")[1]
        for rel in ("returns", "delegates to", "calls"):
            if f" {rel} " in f: a, b = f.split(f" {rel} "); derived[rel].append((a.strip(), b.strip())); break
ret = derived["returns"]
checkable = [(f, ty) for f, ty in ret if f in truth]
ok = [(f, ty) for f, ty in checkable if truth[f] == ty]
rec = {f for f, ty in ok if f in hidden}
reach = {f for f in hidden if any(a == f and b in truth for a, b in t["delegates"])}
print(f"\nreturn types inferred: {len(ret)} | checkable against stubs: {len(checkable)} | correct: {len(ok)}"
      + (f" ({len(ok) / len(checkable):.0%})" if checkable else ""))
print(f"hidden return types recovered: {len(rec)} of {len(hidden)} hidden; of the {len(reach)} reachable through a delegation, {len(rec & reach)} recovered")
print("other inferred facts:", {k: len(v) for k, v in derived.items() if k != "returns"})
wrong = [(f, ty, truth[f]) for f, ty in checkable if truth[f] != ty]
print("wrong examples:", wrong[:8])
print("conflict lines:", sum(1 for l in out.splitlines() if l.startswith("CONFLICT\t")))
