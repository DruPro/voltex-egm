#!/bin/bash
# Gate: with no OBSERVE envelopes, condition D's binary is byte-identical to v2.1 (all defaults).
cd /home/claude/work
NEW=v21/voltex2; D=egm22/voltex2
files="$(ls blind/obs/obs_s*_c*.txt) complex/clean/facts.txt complex/noisy/facts.txt complex/noisy15/facts.txt code/data/code_facts.txt explain/facts.txt v2/data/world_train.txt"
body() { echo "INGESTFILE $1\nRELATIONS\nINFER ALL\nINFER\nCONFLICTS\nCLASSES\nASK ? is from ?\nASK ? is located in ?\nASK ? lives in ?\nSAVE /tmp/ge.vtx2\nLOAD /tmp/ge.vtx2\nINFER ALL\nEXIT\n"; }
a=0; n=0
for f in $files; do
  n=$((n+1))
  x=$(printf "$(body $f)" | $NEW | grep -v "MB/s"); y=$(printf "$(body $f)" | $D | grep -v "MB/s")
  [ "$x" == "$y" ] && a=$((a+1)) || echo "gate differs: $f"
done
x=$(printf "INGESTFILE v2/data/grammar_train.txt\nEVAL v2/data/grammar_unseen.txt\nQUERY the blue ?\nPREDICT ana sells the\nEXIT\n" | $NEW | grep -v "MB/s")
y=$(printf "INGESTFILE v2/data/grammar_train.txt\nEVAL v2/data/grammar_unseen.txt\nQUERY the blue ?\nPREDICT ana sells the\nEXIT\n" | $D | grep -v "MB/s")
n=$((n+1)); [ "$x" == "$y" ] && a=$((a+1)) || echo "gate differs: grammar"
echo "gate (v2.2 without envelopes == v2.1): $a/$n identical"
