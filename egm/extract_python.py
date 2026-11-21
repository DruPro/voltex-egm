"""Static facts for several packages (parse only, never executed). Package-qualified names:
function f / class C / method m of C in package p -> p__f, p__C, p__C_m ; module p/a/b.py -> p__a__b (p/__init__.py -> p__init).
Names that occur twice within a package, or equal a module's id, are dropped (with every fact that mentions them),
so every name is unambiguous.
Relations: is defined in, calls, raises, inherits from, imports. Output: facts text (one per line) + JSON."""
import ast, os, sys, json, builtins, collections
EXC = {n for n in dir(builtins) if isinstance(getattr(builtins, n), type) and issubclass(getattr(builtins, n), BaseException)}
def modules(pkg, root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("tests", "test", "__pycache__")]
        for f in fn:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dp, f), root)[:-3].split(os.sep)
                dotted = [pkg] + rel
                mid = "__".join([pkg] + [("init" if x == "__init__" else x) for x in rel])
                out[mid] = (os.path.join(dp, f), dotted)
    return out
def extract(specs):
    """specs: ["pkg=path/to/pkg", ...] -> {relation: set((a, b))}"""
    facts = collections.defaultdict(set)
    for spec in specs:
        pkg, root = spec.split("=")
        mods = modules(pkg, root)
        dotted2mid = {".".join(d[:-1] if d[-1] == "__init__" else d): m for m, (p, d) in mods.items()}
        trees = {}
        for m, (p, d) in mods.items():
            try: trees[m] = ast.parse(open(p, encoding="utf-8").read())
            except SyntaxError: pass
        defs = collections.defaultdict(list); classes = {}; methods = collections.defaultdict(set); funcs = collections.defaultdict(set)
        for m, t in trees.items():
            for n in t.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): funcs[m].add(n.name); defs[f"{pkg}__{n.name}"].append(m)
                if isinstance(n, ast.ClassDef):
                    classes.setdefault(n.name, []).append((m, [b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else None) for b in n.bases]))
                    defs[f"{pkg}__{n.name}"].append(m)
                    for s in n.body:
                        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)): methods[n.name].add(s.name); defs[f"{pkg}__{n.name}_{s.name}"].append(m)
        unique = {k: v[0] for k, v in defs.items() if len(v) == 1 and k not in mods}   # a def named like a module (p/main.py and main()) is ambiguous too
        cls1 = {c: v[0] for c, v in classes.items() if len(v) == 1}
        def q(name): return f"{pkg}__{name}"
        def mro(c):
            out, todo = [], [c]
            while todo:
                x = todo.pop(0)
                if x in cls1 and x not in out: out.append(x); todo += [b for b in cls1[x][1] if b]
            return out
        def resolve_from(m, node):   # module id targeted by an ImportFrom
            d = mods[m][1]
            if node.level == 0:
                return dotted2mid.get(node.module) if node.module and node.module.split(".")[0] == pkg else None
            base = d[:-1] if d[-1] != "__init__" else d[:-1]
            base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
            tgt = ".".join(base + ([node.module] if node.module else []))
            return dotted2mid.get(tgt)
        imported = collections.defaultdict(dict)
        for m, t in trees.items():
            for n in ast.walk(t):
                if isinstance(n, ast.ImportFrom):
                    tm = resolve_from(m, n)
                    if tm and tm != m: facts["imports"].add((m, tm))
                    for a in n.names:
                        sub = dotted2mid.get(".".join(filter(None, [n.module if n.level == 0 else None])) + "." + a.name) if n.level == 0 and n.module else None
                        if tm: imported[m][a.asname or a.name] = ("obj", a.name, tm)
                if isinstance(n, ast.Import):
                    for a in n.names:
                        if a.name.split(".")[0] == pkg and a.name in dotted2mid and dotted2mid[a.name] != m: facts["imports"].add((m, dotted2mid[a.name]))
        def is_exc(name):
            if name in EXC: return True
            return name in cls1 and any(b in EXC or b.endswith(("Error", "Exception", "Warning")) for c in mro(name) for b in cls1[c][1] if b)
        def exc_of(e):
            if isinstance(e, ast.Call): e = e.func
            nm = e.id if isinstance(e, ast.Name) else (e.attr if isinstance(e, ast.Attribute) else None)
            if not nm or not is_exc(nm): return None
            return q(nm) if nm in cls1 and q(nm) in unique else (nm if nm in EXC else None)
        def body(m, owner, cls, fn):
            for n in ast.walk(fn):
                if isinstance(n, ast.Raise) and n.exc is not None:
                    e = exc_of(n.exc)
                    if e: facts["raises"].add((owner, e))
                if isinstance(n, ast.Call):
                    f = n.func; tgt = None
                    if isinstance(f, ast.Name):
                        if f.id in funcs[m]: tgt = q(f.id)
                        elif f.id in imported[m]:
                            _, nm, tm = imported[m][f.id]
                            if nm in funcs.get(tm, ()): tgt = q(nm)
                    elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self" and cls:
                        for c in mro(cls):
                            if f.attr in methods[c]: tgt = q(f"{c}_{f.attr}"); break
                    if tgt and tgt != owner and tgt in unique: facts["calls"].add((owner, tgt))
        for m, t in trees.items():
            for n in t.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and q(n.name) in unique: body(m, q(n.name), None, n)
                if isinstance(n, ast.ClassDef) and q(n.name) in unique:
                    for b in n.bases:
                        bn = b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else None)
                        if bn: facts["inherits from"].add((q(n.name), q(bn) if bn in cls1 and q(bn) in unique else bn))
                    for s in n.body:
                        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)) and q(f"{n.name}_{s.name}") in unique: body(m, q(f"{n.name}_{s.name}"), n.name, s)
        for k, m in unique.items(): facts["is defined in"].add((k, m))
    return facts


RELATIONS = ["is defined in", "inherits from", "calls", "raises", "imports"]


def write(facts, out_txt, out_json=None):
    with open(out_txt, "w") as f:
        for r in RELATIONS:
            for a, b in sorted(facts[r]):
                f.write(f"{a} {r} {b}\n")
    if out_json:
        json.dump({r: sorted(map(list, facts[r])) for r in RELATIONS}, open(out_json, "w"))
    return {r: len(facts[r]) for r in RELATIONS}
