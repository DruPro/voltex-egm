"""Deterministic fact extraction from one large codebase: the CPython standard library (tests excluded).

  python3 extract.py [--r2] [STDLIB_DIR]     writes ../obs[_r2]/facts.txt, truth.json, key.txt, stats.json

Round 2 (--r2, DEVIATIONS.md entry 1) states the same ast facts in the engine's rule language:
  B is a base of C             the parent-side view of `C inherits from B`, so the base case "a direct base is an
                               ancestor" is an inverse rule (the rule language has no same-direction copy shape)
  F__a0 is first argument of F the slot Python fills first, shaped like a gate's output wire, so a tree rooted at F
                               can decide it; the target becomes `F__a0 is bound to self|cls|nothing`

Every fact comes from Python's own ast, with no heuristics that can be wrong:
  base facts (all stated):
    C inherits from B            a top-level class and a base that resolves to a top-level class in the corpus
                                 (same module, `from m import B`, or `import m` + `m.B`); `object` excluded
    F is a method of C           a def directly in a top-level class body
    C is defined in M            a top-level class and its module
    M is part of P               a module and its parent package (modules inside packages only)
    F has scope class|module     where the def sits
    F has decorator none|staticmethod|classmethod|property   (defs with exactly zero or one of these, nothing else)
  target facts (exact functions of the base facts; truth computed in full here, a seeded share hidden):
    C is a subclass of A         transitive closure of `inherits from`               (depth: needs chained rounds)
    F belongs to package P       method -> class -> module -> package                 (multi-premise: 3 hops)
    F binds self|cls|nothing     what Python passes as the first argument: decided by scope AND decorator
                                 together (no decorator -> self in a class, nothing at module level)   (trees)
Hidden by subject, seed 11: 30% of classes lose all their `is a subclass of` facts, 30% of methods their
`belongs to package` fact, 30% of functions their `binds` fact. truth.json holds every true target fact, so precision
is scored against the complete truth: nothing correct can be scored as wrong for being outside a key.
"""
import ast, collections, glob, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__)); OBS = os.path.join(HERE, "..", "obs")  # round 2: obs_r2
SKIP = ("/test/", "/tests/", "/idle_test/", "/site-packages/", "/dist-packages/", "/__pycache__/", "/lib2to3/")
DECOS = {"staticmethod", "classmethod", "property"}
# exploratory depth stress (--hide-sub 0.7, writes ../obs_depth): hide the ancestry of more classes, so that parents are
# often hidden too and answers must be built over several rounds. The other hidden sets are unchanged.
HIDE_SUB = 0.30


def tok(*parts): return "__".join(p.replace(".", "__") for p in parts if p)


def modname(root, path):
    rel = os.path.relpath(path, root)[:-3].replace(os.sep, ".")
    return rel[:-9] if rel.endswith(".__init__") else rel


def main(root, r2=False):
    files = sorted(p for p in glob.glob(os.path.join(root, "**", "*.py"), recursive=True)
                   if not any(s in p.replace(os.sep, "/") + "/" or s in p for s in SKIP)
                   and "-" not in os.path.relpath(p, root))
    trees, lines = {}, 0
    for p in files:
        src = open(p, encoding="utf-8", errors="replace").read()
        try: trees[modname(root, p)] = (ast.parse(src), p.endswith("__init__.py"))
        except SyntaxError: continue
        lines += src.count("\n")
    classes = {m: {n.name for n in t.body if isinstance(n, ast.ClassDef)} for m, (t, _) in trees.items()}
    base, funcs = set(), {}
    inherits = collections.defaultdict(set)
    for m, (t, ispkg) in trees.items():
        pkg = m if ispkg else m.rpartition(".")[0]
        names, mods = {}, {}
        for n in ast.walk(t):
            if isinstance(n, ast.ImportFrom) and n.module is not None:
                src = n.module
                if n.level: src = ".".join(pkg.split(".")[: len(pkg.split(".")) - n.level + 1] + ([n.module] if n.module else []))
                for a in n.names: names[a.asname or a.name] = (src, a.name)
            elif isinstance(n, ast.Import):
                for a in n.names: mods[a.asname or a.name] = a.name
        if "." in m: base.add(f"{tok(m)} is part of {tok(m.rpartition('.')[0])}")
        def resolve(b):
            if isinstance(b, ast.Name):
                if b.id in classes[m]: return (m, b.id)
                if b.id in names and names[b.id][1] in classes.get(names[b.id][0], ()): return names[b.id]
            if isinstance(b, ast.Attribute) and isinstance(b.value, ast.Name) and b.value.id in mods:
                mm = mods[b.value.id]
                if b.attr in classes.get(mm, ()): return (mm, b.attr)
            return None
        def fn(f, scope, owner):
            ds = [d.id if isinstance(d, ast.Name) else None for d in f.decorator_list]
            if len(ds) > 1 or (ds and ds[0] not in DECOS): return
            if scope == "module" and ds: return
            funcs[tok(owner, f.name)] = (scope, ds[0] if ds else "none")
        for n in t.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): fn(n, "module", m)
            if not isinstance(n, ast.ClassDef): continue
            c = tok(m, n.name)
            base.add(f"{c} is defined in {tok(m)}")
            for b in n.bases:
                r = resolve(b)
                if r and r != (m, n.name):
                    base.add(f"{c} inherits from {tok(*r)}"); inherits[c].add(tok(*r))
                    if r2: base.add(f"{tok(*r)} is a base of {c}")
            for f in n.body:
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    base.add(f"{tok(m, n.name, f.name)} is a method of {c}"); fn(f, "class", f"{m}.{n.name}")
    # targets, computed in full
    def closure(c, seen=None):
        seen = set() if seen is None else seen
        for b in inherits.get(c, ()):
            if b not in seen: seen.add(b); closure(b, seen)
        return seen
    sub = {f"{c} is a subclass of {a}" for c in inherits for a in closure(c) if a != c}
    rel = collections.defaultdict(dict)
    for f in base:
        s, _, o = f.partition(" "); r, o = o.rsplit(" ", 1); rel[r][s] = o
    pkg_of = {}
    for meth, cls in rel["is a method of"].items():
        mod = rel["is defined in"].get(cls); p = rel["is part of"].get(mod)
        if p: pkg_of[meth] = f"{meth} belongs to package {p}"
    for f, (scope, d) in funcs.items():
        base.add(f"{f} has scope {scope}"); base.add(f"{f} has decorator {d}")
        if r2: base.add(f"{f}__a0 is first argument of {f}")
    BIND = {("class", "none"): "self", ("class", "property"): "self", ("class", "classmethod"): "cls",
            ("class", "staticmethod"): "nothing", ("module", "none"): "nothing"}
    binds = {f: (f"{f}__a0 is bound to {BIND[v]}" if r2 else f"{f} binds {BIND[v]}") for f, v in funcs.items()}
    rr = random.Random(11)
    hide = lambda xs, p=0.30: {x for x in sorted(xs) if rr.random() < p}
    hc, hm, hf = hide(inherits, HIDE_SUB), hide(pkg_of), hide(binds)
    stated_t = {f for f in sub if f.split(" ")[0] not in hc} | {v for k, v in pkg_of.items() if k not in hm} \
        | {v for k, v in binds.items() if k not in hf}
    truth = sorted(sub | set(pkg_of.values()) | set(binds.values()))
    key = sorted(set(truth) - stated_t)
    global OBS
    if r2: OBS = OBS + "_r2"
    if HIDE_SUB != 0.30: OBS = os.path.join(HERE, "..", "obs_depth")
    os.makedirs(OBS, exist_ok=True)
    facts = sorted(base | stated_t)
    open(os.path.join(OBS, "facts.txt"), "w").write("\n".join(facts) + "\n")
    open(os.path.join(OBS, "key.txt"), "w").write("\n".join(key) + "\n")
    json.dump({"base": sorted(base), "targets": truth}, open(os.path.join(OBS, "truth.json"), "w"))
    words = {w for f in facts for w in f.split()}
    depth = max((len(closure(c)) for c in inherits), default=0)
    st = {"python": sys.version.split()[0], "files": len(trees), "lines": lines, "facts": len(facts),
          "words": len(words), "truth_targets": len(truth), "hidden": len(key),
          "by_relation": dict(collections.Counter(f.split(" ", 1)[1].rsplit(" ", 1)[0] for f in facts)),
          "hidden_by_relation": dict(collections.Counter(f.split(" ", 1)[1].rsplit(" ", 1)[0] for f in key)),
          "max_ancestors": depth}
    json.dump(st, open(os.path.join(OBS, "stats.json"), "w"), indent=1); print(json.dumps(st, indent=1))


if __name__ == "__main__":
    if "--hide-sub" in sys.argv:
        i = sys.argv.index("--hide-sub"); HIDE_SUB = float(sys.argv[i + 1]); del sys.argv[i:i + 2]
    a = [x for x in sys.argv[1:] if x != "--r2"]
    main(a[0] if a else "/usr/lib/python3.13", "--r2" in sys.argv)
