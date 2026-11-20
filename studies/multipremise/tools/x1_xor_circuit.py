"""Exploratory X1: can the rule shapes (CHAIN up to 4, CONDITIONS) learn a XOR gate from examples?
300 gates with random inputs; output values given for 200 gates (teaching), hidden for 100."""
import random, subprocess
E = "/home/claude/work/multipremise/voltex2"
r = random.Random(1); lines = []; hidden = {}
names = iter(f"{a}{b}{c}{d}" for a in "bdfgklmnprstvz" for b in "aeiou" for c in "bdfgklmnprstvz" for d in "aeiou")
word = {0: "zero", 1: "one"}
for g in range(300):
    gate, w1, w2, w3 = next(names), next(names), next(names), next(names)
    a, b = r.randint(0, 1), r.randint(0, 1); out = a ^ b
    lines += [f"{w3} is output of {gate}", f"{gate} has first input {w1}", f"{gate} has second input {w2}", f"{gate} has kind xor",
              f"{w1} has value {word[a]}", f"{w2} has value {word[b]}"]
    if g < 200: lines.append(f"{w3} has value {word[out]}")
    else: hidden[w3] = word[out]
r.shuffle(lines); open("obs/xor.txt", "w").write("\n".join(lines) + "\n")
for sets in (["SET CHAIN 2"], ["SET CHAIN 4"], ["SET CHAIN 4", "SET CONDITIONS 1"]):
    txt = subprocess.run([E], input="\n".join(sets + ["INGESTFILE obs/xor.txt", "RELATIONS", "INFER ALL", "EXIT"]) + "\n", capture_output=True, text=True).stdout
    got = {}
    for l in txt.splitlines():
        if l.startswith("FACT\t") and " has value " in l:
            w, v = l.split("\t")[1].split(" has value "); got[w.strip()] = v.strip()
    right = sum(1 for w, v in got.items() if hidden.get(w) == v); wrong = sum(1 for w, v in got.items() if w in hidden and hidden[w] != v)
    acc = [l.strip()[:150] for l in txt.splitlines() if l.strip().startswith("ACCEPT") and "has value" in l.split("=>")[-1]]
    print(f"{' + '.join(sets)}: hidden outputs right {right}/100, wrong {wrong} | rules concluding 'has value': {len(acc)}")
    for a in acc[:4]: print("     ", a)
