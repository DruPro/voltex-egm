#!/bin/bash
# H0: with no AMEND commands, the AMEND build must match v2.1 byte for byte (all defaults on).
cd /home/claude/work
NEW=v21/voltex2; AM=amend/voltex2_amend
files="$(ls blind/obs/obs_s*_c*.txt) complex/clean/facts.txt complex/noisy/facts.txt complex/noisy15/facts.txt code/data/code_facts.txt explain/facts.txt v2/data/world_train.txt"
body() { echo "INGESTFILE $1\nRELATIONS\nINFER ALL\nINFER\nCONFLICTS\nCLASSES\nASK ? is from ?\nASK ? is located in ?\nSAVE /tmp/h0.vtx2\nLOAD /tmp/h0.vtx2\nINFER ALL\nEXIT\n"; }
a=0; n=0
for f in $files; do
  n=$((n+1))
  x=$(printf "$(body $f)" | $NEW | grep -v "MB/s")
  y=$(printf "$(body $f)" | $AM | grep -v "MB/s")
  [ "$x" == "$y" ] && a=$((a+1)) || echo "H0 differs: $f"
done
# UPDATE path must also be untouched
f=blind/obs/obs_s1_c50.txt; p=$(grep " lives in " $f | head -1 | awk '{print $1}')
cmd="INGESTFILE $f\nUPDATE $p lives in zzzplace\nINFER ALL\nCONFLICTS\nEXIT\n"
x=$(printf "$cmd" | $NEW | grep -v "MB/s"); y=$(printf "$cmd" | $AM | grep -v "MB/s"); n=$((n+1))
[ "$x" == "$y" ] && a=$((a+1)) || echo "H0 differs: UPDATE path"
echo "H0 gate: $a/$n identical"
