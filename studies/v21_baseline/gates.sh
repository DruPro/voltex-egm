#!/bin/bash
# Gate A: v2.1 with its four behaviours off  == frozen v2.0, byte for byte.
# Gate B: v2.1 defaults                      == experimental build with the adopted switches (tier markers normalised).
cd /home/claude/work
FROZEN=blind/frozen/voltex2; NEW=v21/voltex2; EXP=improve/voltex2_exp
files="$(ls blind/obs/obs_s*_c*.txt) complex/clean/facts.txt complex/noisy/facts.txt complex/noisy15/facts.txt code/data/code_facts.txt explain/facts.txt v2/data/world_train.txt"
body() { echo "INGESTFILE $1\nRELATIONS\nINFER ALL\nINFER\nCONFLICTS\nCLASSES\nASK ? is from ?\nASK ? is located in ?\nSAVE /tmp/g.vtx2\nLOAD /tmp/g.vtx2\nINFER ALL\nEXIT\n"; }
norm() { grep -v "MB/s" | sed -E 's/ \[(law|tendency)\]//; s/\[(law|tendency)\] //'; }
a=0; b=0; n=0
for f in $files; do
  n=$((n+1))
  x=$(printf "$(body $f)" | $FROZEN | grep -v "MB/s")
  y=$(printf "SET COVERAGE 0\nSET LABELS 0\nSET CORROBORATE 0\nSET STALE 0\n$(body $f)" | $NEW | grep -v "MB/s" | grep -v "^\[SET\]")
  [ "$x" == "$y" ] && a=$((a+1)) || echo "gate A differs: $f"
  x=$(printf "SET COV 2\nSET TIERS 2\nSET STALE 1\n$(body $f)" | $EXP | norm | grep -v "^\[SET\]")
  y=$(printf "$(body $f)" | $NEW | norm)
  [ "$x" == "$y" ] && b=$((b+1)) || echo "gate B differs: $f"
done
x=$(printf "INGESTFILE v2/data/grammar_train.txt\nEVAL v2/data/grammar_unseen.txt\nQUERY the blue ?\nPREDICT ana sells the\nEXIT\n" | $FROZEN | grep -v "MB/s")
y=$(printf "SET COVERAGE 0\nSET LABELS 0\nSET CORROBORATE 0\nSET STALE 0\nINGESTFILE v2/data/grammar_train.txt\nEVAL v2/data/grammar_unseen.txt\nQUERY the blue ?\nPREDICT ana sells the\nEXIT\n" | $NEW | grep -v "MB/s" | grep -v "^\[SET\]")
n=$((n+1)); [ "$x" == "$y" ] && a=$((a+1)) || echo "gate A differs: grammar"
echo "gate A (v2.1 off == v2.0): $a/$n identical"
echo "gate B (v2.1 defaults == tested experimental configuration): $b/$((n-1)) identical"
