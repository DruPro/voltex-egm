"""H1 world: 40 five-generation binary-tree families. Writes obs/lineage_s<seed>.txt (what the engine sees) and hidden/lineage_s<seed>.json (truth)."""
import json, random, sys
def gen(seed):
    r = random.Random(seed)
    syl = ["ka", "mo", "ri", "tu", "se", "ne", "lo", "fa", "di", "ze", "bo", "ja", "vu", "pe", "xi", "go"]
    names = sorted({a + b + c for a in syl for b in syl for c in syl}); r.shuffle(names); it = iter(names)
    parent, gg, ggg, fam_of = [], [], [], {}
    for f in range(40):
        gens = [[next(it)]]
        for g in range(1, 5):
            gens.append([])
            for p in gens[g - 1]:
                for _ in range(2):
                    c = next(it); gens[g].append(c); parent.append((p, c))
        for p in sum(gens, []): fam_of[p] = f
        kids = {}
        for a, b in parent: kids.setdefault(a, []).append(b)
        def desc(x, d):
            cur = [x]
            for _ in range(d): cur = [k for y in cur for k in kids.get(y, [])]
            return cur
        for g in range(2):
            for x in gens[g]: gg += [(x, y) for y in desc(x, 3)]
        ggg += [(gens[0][0], y) for y in desc(gens[0][0], 4)]
    taught = set(range(25))
    lines = [f"{a} is parent of {b}" for a, b in parent]
    lines += [f"{a} is great grandparent of {b}" for a, b in gg if fam_of[a] in taught]
    lines += [f"{a} is great great grandparent of {b}" for a, b in ggg if fam_of[a] in taught]
    r.shuffle(lines)
    unseen = lambda xs: [p for p in xs if fam_of[p[0]] not in taught]
    return lines, {"gg": gg, "ggg": ggg, "gg_unseen": unseen(gg), "ggg_unseen": unseen(ggg), "parent": parent}
if __name__ == "__main__":
    for s in range(5):
        lines, truth = gen(s)
        open(f"obs/lineage_s{s}.txt", "w").write("\n".join(lines) + "\n"); json.dump(truth, open(f"hidden/lineage_s{s}.json", "w"))
        print(s, len(lines), "lines |", len(truth["gg_unseen"]), "unseen great-grandparent,", len(truth["ggg_unseen"]), "unseen great-great")
