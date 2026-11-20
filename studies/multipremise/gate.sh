#!/bin/bash
# G1: every new switch at its default == frozen 2.2.1 (DruPro/voltex-egm src/voltex2.cpp), byte for byte.
cd /home/claude/work
A=${A:-multipremise/frozen_voltex2}; B=${B:-multipremise/voltex2}
files="$(ls blind/obs/obs_s*_c*.txt) complex/clean/facts.txt complex/noisy/facts.txt complex/noisy15/facts.txt code/data/code_facts.txt explain/facts.txt v2/data/world_train.txt scale_econ/corpus/M.txt"
body() { echo "INGESTFILE $1\nRELATIONS\nINFER ALL\nINFER\nCONFLICTS\nCLASSES\nASK ? is from ?\nASK ? is located in ?\nASK ? lives in ?\nSAVE /tmp/gm.vtx2\nLOAD /tmp/gm.vtx2\nINFER ALL\nEXIT\n"; }
a=0; n=0
for f in $files; do n=$((n+1)); x=$(printf "$(body $f)" | $A | grep -v "MB/s"); y=$(printf "$(body $f)" | $B | grep -v "MB/s"); [ "$x" == "$y" ] && a=$((a+1)) || echo "differs: $f"; done
echo "gate: $a/$n identical"
