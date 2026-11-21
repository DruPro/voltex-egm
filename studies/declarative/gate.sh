#!/bin/bash
# Gate 1: condition-C build with interpretation off == v2.1, byte for byte.
# Gate 2: interpretation on, no amendment records: identical except contradiction reports.
cd /home/claude/work
NEW=v21/voltex2; C=declarative/voltex2_decl
files="$(ls blind/obs/obs_s*_c*.txt) complex/clean/facts.txt complex/noisy/facts.txt complex/noisy15/facts.txt code/data/code_facts.txt explain/facts.txt v2/data/world_train.txt"
body() { echo "INGESTFILE $1\nRELATIONS\nINFER ALL\nINFER\nCONFLICTS\nCLASSES\nASK ? is from ?\nASK ? is located in ?\nASK ? lives in ?\nSAVE /tmp/gd.vtx2\nLOAD /tmp/gd.vtx2\nINFER ALL\nEXIT\n"; }
strip() { grep -v "MB/s" | grep -v "^CONFLICT.*CONTRADICTION" | grep -v "^\[CONFLICTS\]" | sed -E 's/ stated, CONTRADICTED: .*/ stated/' | sed -E 's/ +$//'; }
a=0; b=0; n=0
for f in $files; do
  n=$((n+1))
  x=$(printf "$(body $f)" | $NEW | grep -v "MB/s"); y=$(printf "SET DECL 0\n$(body $f)" | $C | grep -v "MB/s" | grep -v "^\[SET\]")
  [ "$x" == "$y" ] && a=$((a+1)) || echo "gate 1 differs: $f"
  x=$(printf "$(body $f)" | $NEW | strip); y=$(printf "$(body $f)" | $C | strip)
  [ "$x" == "$y" ] && b=$((b+1)) || echo "gate 2 differs: $f"
done
echo "gate 1 (interpretation off == v2.1): $a/$n identical"
echo "gate 2 (on, no amendment records == v2.1 apart from contradiction reports): $b/$n identical"
