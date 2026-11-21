"""A harder world: a 450-person company with multi-hop structure, gaps, noise and decoys.
Usage: python3 gen_company.py <noise_fraction> <outdir>"""
import random, json, sys, os
noise = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
out = sys.argv[2] if len(sys.argv) > 2 else "clean"
os.makedirs(out, exist_ok=True)
r = random.Random(21)
syl = ["ka", "lo", "mi", "ne", "ru", "sa", "ti", "vo", "ze", "pa", "do", "fi", "gu", "he", "jo", "be"]
used = set()
def nm():
    while True:
        s = "".join(r.choice(syl) for _ in range(3))
        if s not in used: used.add(s); return s

cities = ["denver", "boston", "austin", "seattle", "miami", "chicago"]
depts = ["sales", "legal", "finance", "research", "support", "design", "security", "logistics"]
dept_city = {d: cities[i % 6] for i, d in enumerate(depts)}
vps = [nm(), nm()]
director = {d: nm() for d in depts}
teams = [f"team{i:02d}" for i in range(40)]
team_dept = {t: depts[i % 8] for i, t in enumerate(teams)}
lead = {t: nm() for t in teams}
members = {t: [nm() for _ in range(10)] for t in teams}
foods = ["pizza", "sushi", "tacos", "curry", "salad", "ramen", "pasta", "soup", "burgers", "dumplings"]

T = {k: set() for k in ["is based in", "is on", "belongs to", "works under", "collaborates with", "knows", "likes"]}
S = {k: set() for k in T}   # stated
# --- location chain: person -> team -> department -> city (3 hops) ---
for d in depts: T["is based in"].add((d, dept_city[d])); S["is based in"].add((d, dept_city[d]))
for t in teams:
    T["belongs to"].add((t, team_dept[t])); S["belongs to"].add((t, team_dept[t]))
    c = dept_city[team_dept[t]]; T["is based in"].add((t, c))
    if r.random() < 0.5: S["is based in"].add((t, c))
person_team = {}
for t in teams:
    for p in members[t] + [lead[t]]:
        person_team[p] = t; T["is on"].add((p, t)); S["is on"].add((p, t))
        c = dept_city[team_dept[t]]; T["is based in"].add((p, c))
        if r.random() < 0.3: S["is based in"].add((p, c))
# --- reporting line: member -> lead -> director -> vp (transitive) ---
up = {}
for t in teams:
    for m in members[t]: up[m] = lead[t]
    up[lead[t]] = director[team_dept[t]]
for i, d in enumerate(depts): up[director[d]] = vps[i % 2]
for p in up:
    x = p; first = True
    while x in up:
        x = up[x]; T["works under"].add((p, x))
        if first or r.random() < 0.3: S["works under"].add((p, x))
        first = False
# --- collaboration: symmetric, often stated one way only ---
for t in teams:
    for m in members[t]:
        for q in r.sample([x for x in members[t] if x != m], 2):
            T["collaborates with"] |= {(m, q), (q, m)}
            S["collaborates with"].add((m, q))
            if r.random() < 0.6: S["collaborates with"].add((q, m))
# --- decoys: no rule should ever fire from these ---
everyone = list(person_team)
for p in everyone:
    for q in r.sample(everyone, 2):
        if q != p: T["knows"].add((p, q)); S["knows"].add((p, q))
    f = r.choice(foods); T["likes"].add((p, f)); S["likes"].add((p, f))
# --- noise: replace a fraction of stated person cities with a wrong city ---
corrupted = []
if noise > 0:
    person_facts = sorted(f for f in S["is based in"] if f[0] in person_team)
    for f in r.sample(person_facts, int(noise * len(person_facts))):
        wrong = r.choice([c for c in cities if c != f[1]])
        S["is based in"].discard(f); S["is based in"].add((f[0], wrong)); corrupted.append([f[0], f[1], wrong])
lines = [f"{a} {rel} {b}" for rel, fs in S.items() for a, b in sorted(fs)]
r.shuffle(lines)
open(f"{out}/facts.txt", "w").write("\n".join(lines) + "\n")
json.dump({"truth": {k: sorted(v) for k, v in T.items()}, "stated": {k: sorted(v) for k, v in S.items()}, "corrupted": corrupted},
          open(f"{out}/truth.json", "w"))
print(f"{out}: {len(lines)} stated facts | unstated true facts:",
      {k: len(T[k] - S[k]) for k in T if T[k] - S[k]}, "| corrupted:", len(corrupted))
