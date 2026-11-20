#!/bin/bash
# Gate: with every experimental switch off, voltex2_exp must produce output identical to the frozen binary.
cd /home/claude/work
FROZEN=blind/frozen/voltex2; EXP=improve/voltex2_exp; fails=0; n=0
files="$(ls blind/obs/obs_s*_c*.txt) complex/clean/facts.txt complex/noisy/facts.txt complex/noisy15/facts.txt code/data/code_facts.txt explain/facts.txt v2/data/world_train.txt"
for f in $files; do
  cmds="INGESTFILE $f\nRELATIONS\nINFER ALL\nCONFLICTS\nCLASSES\nASK ? is from ?\nSAVE /tmp/gate.vtx2\nLOAD /tmp/gate.vtx2\nINFER ALL\nEXIT\n"
  a=$(printf "$cmds" | $FROZEN | grep -v "MB/s")
  b=$(printf "$cmds" | $EXP | grep -v "MB/s")
  n=$((n+1)); if [ "$a" != "$b" ]; then echo "DIFF: $f"; fails=$((fails+1)); fi
done
a=$(printf "INGESTFILE v2/data/grammar_train.txt\nEVAL v2/data/grammar_unseen.txt\nQUERY the blue ?\nEXIT\n" | $FROZEN | grep -v "MB/s")
b=$(printf "INGESTFILE v2/data/grammar_train.txt\nEVAL v2/data/grammar_unseen.txt\nQUERY the blue ?\nEXIT\n" | $EXP | grep -v "MB/s")
n=$((n+1)); [ "$a" != "$b" ] && { echo "DIFF: grammar eval"; fails=$((fails+1)); }
echo "regression gate: $((n-fails))/$n datasets identical"
