import random, subprocess, json, sys
E="/home/claude/work/egm-kit/build/voltex2"
def world(fams, frac, seed, noise=0.0):
    r=random.Random(seed)
    names=[f"{a}{b}{c}" for a in "bdfgklmnprstvz" for b in "aeiou" for c in ["ra","lo","mi","ten","vik","sa"]]; r.shuffle(names); it=iter(names)
    facts=[]; gp=[]
    for f in range(fams):
        g=next(it)
        for _ in range(2):
            p=next(it); facts.append(f"{g} is parent of {p}")
            for _ in range(2):
                c=next(it); facts.append(f"{p} is parent of {c}"); gp.append((g,c))
    r.shuffle(gp); k=int(round(len(gp)*frac)); shown, hidden=gp[:k], gp[k:]
    ex=[f"{a} is grandparent of {b}" for a,b in shown]
    allnames=[x for f in facts for x in (f.split()[0], f.split()[-1])]
    nbad=int(round(len(ex)*noise))
    for i in range(nbad): ex[i]=f"{r.choice(allnames)} is grandparent of {r.choice(allnames)}"
    return facts+ex, set(hidden), set(shown)
def run(fams, frac, seed, noise=0.0):
    lines, hidden, shown = world(fams, frac, seed, noise)
    open("/tmp/pbe.txt","w").write("\n".join(lines)+"\n")
    out=subprocess.run([E],input="INGESTFILE /tmp/pbe.txt\nRELATIONS\nINFER ALL\nEXIT\n",capture_output=True,text=True).stdout
    rule=[l.strip() for l in out.splitlines() if "is grandparent of ?](a,c)" in l and "is parent of ?](b,c)" in l and "[? is parent of ?](a,b)" in l]
    acc=bool(rule) and rule[0].startswith("ACCEPT"); tier=(rule[0].split("tier=")[1] if rule and "tier=" in rule[0] else "-")
    d=[tuple(l.split("\t")[1].split(" is grandparent of ")) for l in out.splitlines() if l.startswith("FACT\t") and " is grandparent of " in l]
    right=sum(x in hidden for x in d); wrong=sum(x not in hidden and x not in shown for x in d)
    return acc, tier, right, len(hidden), wrong
print("families shown% noise | rule accepted (tier) | hidden grandparents recovered | wrong inferences   [mean over 5 seeds]")
for fams, frac, noise in [(6,0.5,0),(6,0.75,0),(30,0.25,0),(30,0.5,0),(30,0.75,0),(30,0.5,0.2),(30,0.5,0.4)]:
    rs=[run(fams,frac,s,noise) for s in range(5)]
    acc=sum(r[0] for r in rs); tiers=sorted({r[1] for r in rs if r[0]}); rec=sum(r[2] for r in rs)/sum(r[3] for r in rs); wr=sum(r[4] for r in rs)/5
    print(f"{fams:4d} {int(frac*100):6d}% {int(noise*100):4d}% | {acc}/5 accepted {','.join(tiers) or '':9s} | recall {rec:5.2f} | wrong {wr:5.1f}")
