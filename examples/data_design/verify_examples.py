"""Reruns every example in docs/DATA_DESIGN.md and checks the numbers the guide quotes.
Usage: python3 examples/data_design/verify_examples.py   (uses $VOLTEX or build/voltex2)"""
import os, random, sys, tempfile
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
import egm, worlds  # noqa: E402

checks = []


def check(name, ok, detail=""):
    checks.append(ok); print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def kb(lines, **settings):
    td = tempfile.mkdtemp(); p = os.path.join(td, "facts.txt")
    with open(p, "w") as f: f.write("\n".join(lines) + "\n")
    return egm.open(p, settings=settings)


def names(n, prefix): return [f"{prefix}{i:02d}" for i in range(n)]


def office(city0="oslo", phrase="has headquarters in"):
    comp, cities, ppl, L = names(8, "acme"), [city0, "rome", "lima", "kyiv"], names(80, "emp"), []
    for i, c in enumerate(comp): L.append(f"{c} {phrase} {cities[i % 4]}")
    for i, p in enumerate(ppl):
        L.append(f"{p} works at {comp[i % 8]}")
        if i < 70: L.append(f"{p} is based in {cities[(i % 8) % 4]}")
    return L


# 1.1 relation phrasing and one-word entities
with kb(office()) as e:
    r = [x for x in e.rules() if "has headquarters in" in x.text]
    a = [f for f in e.ask("emp75 is based in ?") if f.status == "inferred"]
    check("1.1 office chain is a law and answers emp75", bool(r) and r[0].tier == "law" and a and a[0].object == "kyiv" and a[0].tier == "law")
with kb(office(phrase="is located in")) as e:
    check("1.1 'is located in' next to 'is based in' gives no rule", not e.rules(), str([x.template for x in e.relations()][:3]))
with kb(office(city0="new york")) as e:
    facts = {x.relation: x.facts for x in e.relations()}
    check("1.1 'new york' drops facts (70 -> 52 city facts, 8 -> 6 office facts)", facts.get("is based in") == 52 and facts.get("has headquarters in") == 6, str(facts))
    check("1.1 'new york': no answer for a New York employee", not [f for f in e.ask("emp72 is based in ?") if f.status == "inferred"])
with kb(office(city0="new_york")) as e:
    a = [f for f in e.ask("emp72 is based in ?") if f.status == "inferred"]
    check("1.1 'new_york' keeps every fact and answers", a and a[0].object == "new_york")


# 2.1 inverse, completeness decides the tier
def boxes(k):
    L = []
    for i, it in enumerate(names(60, "item")):
        b = f"box{i % 10:02d}"; L.append(f"{it} is in {b}")
        if i < k: L.append(f"{b} contains {it}")
    return L
for k, tier in ((40, "tendency"), (57, "law")):
    with kb(boxes(k)) as e:
        r = [x for x in e.rules() if x.text.startswith("[? is in ?]")]
        check(f"2.1 'is in => contains' with {k} of 60 stated is {tier}", bool(r) and r[0].tier == tier, f"agree {r[0].agree if r else None}")

# 2.2 longer path
L, unseen = worlds.lineage()
with kb(L) as e:
    check("2.2 CHAIN 2: no great-grandparent inferred", not [f for f in e.infer_all() if f.relation == "is great grandparent of"])
with kb(L, CHAIN=3) as e:
    got = {(f.subject, f.object) for f in e.infer_all() if f.relation == "is great grandparent of"}
    check("2.2 CHAIN 3: all 80 unstated great-grandparents, 0 wrong", got == unseen and len(got) == 80)

# 2.3 rule for a group
L, wrong = worlds.harvest()
with kb(L, CONDITIONS=1) as e:
    r = [x for x in e.rules() if x.condition]
    check("2.3 CONDITIONS restricts harvest to farmers and miners", r and "farmer" in r[0].condition and "miner" in r[0].condition)


# 2.4 tree decision table, and the random control
def orders(random_ship=False):
    r = random.Random(3 if not random_ship else 5); L, hidden = [], {}
    cust = names(60, "cust"); tier, reg = {}, {}
    for c in cust:
        tier[c] = r.choice(["gold", "basic"]); reg[c] = r.choice(["north", "south"])
        L += [f"{c} has tier {tier[c]}", f"{c} lives in region {reg[c]}"]
        if random_ship: L.append(f"{c} likes color {r.choice(['red', 'blue', 'green'])}")
    for i in range(400):
        o = f"order{i:03d}"; c = r.choice(cust); L.append(f"{o} was placed by {c}")
        ship = r.choice(["express", "standard"]) if random_ship else ("express" if tier[c] == "gold" and reg[c] == "north" else "standard")
        if r.random() < 2 / 3: L.append(f"{o} ships {ship}")
        else: hidden[o] = ship
    return L, hidden
L, hidden = orders()
with kb(L) as e:
    check("2.4 without TREES nothing is inferred", not [f for f in e.infer_all() if f.relation == "ships"])
with kb(L, TREES=1) as e:
    got = {f.subject: f.object for f in e.infer_all() if f.relation == "ships"}
    trees = e.rules(shape="tree")
    check("2.4 TREES: 133 of 133 hidden orders, 0 wrong, 4 law-tier tree rules", len(hidden) == 133 and all(got.get(o) == v for o, v in hidden.items())
          and len(got) == 133 and len(trees) == 4 and all(t.tier == "law" for t in trees)
          and any("=> [? has tier ?](a,gold)" in t.text for t in trees),
          f"hidden {len(hidden)}, right {sum(got.get(o) == v for o, v in hidden.items())}, derived {len(got)}, tree rules {[t.tier for t in trees]}")
L, _ = orders(random_ship=True)
with kb(L, TREES=1) as e:
    check("2.4 control: random shipping gives 0 rules, 0 facts", not e.rules() and not e.infer_all())

# 3 wholly unanswered vs partly answered: covered by 1.1 (law with 70 of 80) and 2.1 (tendency with 40 of 60)

# 5.1 two stages
L, hidden = orders()
truth = {}
r = random.Random(3); cust = names(60, "cust"); tier, reg = {}, {}
for c in cust: tier[c] = r.choice(["gold", "basic"]); reg[c] = r.choice(["north", "south"])
for i in range(400):
    o = f"order{i:03d}"; c = r.choice(cust); truth[o] = "fastco" if tier[c] == "gold" and reg[c] == "north" else "slowco"; r.random()
taught = [o for o in sorted(truth) if o not in hidden][:150]
B = ["express is handled by fastco", "standard is handled by slowco", "overnight is handled by fastco", "freight is handled by slowco",
     "bulk is handled by slowco"] + [f"{o} goes with {truth[o]}" for o in taught]
with kb(L, TREES=1) as a:
    ders = a.infer_all(); law = [f.fact for f in ders if f.tier == "law"]
    check("5.1 stage A: 133 law-tier facts, 0 tendency", len(law) == 133 and len(ders) == 133)
with kb([l for l in L if " ships " in l] + law + B) as b:
    got = {f.subject: f.object for f in b.infer_all() if f.relation == "goes with"}
ev = [o for o in truth if o not in taught]
check("5.1 stage B: 250 of 250 untaught orders, 0 wrong", len(ev) == 250 and all(got.get(o) == truth[o] for o in ev))
with kb(L + B, TREES=1) as e:
    got = {f.subject: f.object for f in e.infer_all() if f.relation == "goes with"}
check("5.1 one engine with everything: also 250 of 250", all(got.get(o) == truth[o] for o in ev))

print(f"\n{sum(checks)} of {len(checks)} checks passed")
sys.exit(0 if all(checks) else 1)
