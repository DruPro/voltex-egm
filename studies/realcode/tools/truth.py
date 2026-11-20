"""Static ground truth for a Python package (parse only, never executed).
Names: function f -> 'f'; method m of class C -> 'C_m'; class -> 'C'; module requests/x.py -> 'x'.
Relations: defined in, calls (only calls that resolve statically to package functions/methods), raises, inherits from, imports."""
import ast, os, sys, json, builtins
src_dir, out = sys.argv[1], sys.argv[2]
mods = {f[:-3]: os.path.join(src_dir, f) for f in sorted(os.listdir(src_dir)) if f.endswith(".py")}
trees = {m: ast.parse(open(p, encoding="utf-8").read()) for m, p in mods.items()}
defined, classes, methods, funcs = {}, {}, {}, {}
for m, t in trees.items():
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): funcs.setdefault(m, set()).add(n.name); defined[n.name] = m
        if isinstance(n, ast.ClassDef):
            classes[n.name] = (m, [b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else None) for b in n.bases])
            defined[n.name] = m
            for s in n.body:
                if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)): methods.setdefault(n.name, set()).add(s.name); defined[f"{n.name}_{s.name}"] = m
def mro(c):   # package-internal linearisation (depth-first, good enough for single inheritance chains)
    out, todo = [], [c]
    while todo:
        x = todo.pop(0)
        if x in classes and x not in out: out.append(x); todo += [b for b in classes[x][1] if b]
    return out
imported = {m: {} for m in trees}   # module -> local name -> package object or module
imports = set()
for m, t in trees.items():
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and n.level >= 1:
            if n.module:
                if n.module in mods: imports.add((m, n.module))
                for a in n.names: imported[m][a.asname or a.name] = ("obj", a.name, n.module)
            else:
                for a in n.names:
                    if a.name in mods: imports.add((m, a.name)); imported[m][a.asname or a.name] = ("mod", a.name)
EXC = {n for n in dir(builtins) if isinstance(getattr(builtins, n), type) and issubclass(getattr(builtins, n), BaseException)}
def exc_name(e):
    if isinstance(e, ast.Call): e = e.func
    if isinstance(e, ast.Name): name = e.id
    elif isinstance(e, ast.Attribute): name = e.attr
    else: return None
    return name if (name in EXC or (name in classes and any(b in EXC or b in classes for b in mro(name)))) else None
calls, raises = set(), set()
def visit_body(m, owner, fn):
    for n in ast.walk(fn):
        if isinstance(n, ast.Raise) and n.exc is not None:
            e = exc_name(n.exc)
            if e: raises.add((owner, e))
        if isinstance(n, ast.Call):
            f = n.func; tgt = None
            if isinstance(f, ast.Name):
                nm = f.id
                if nm in funcs.get(m, ()): tgt = nm
                elif nm in imported[m] and imported[m][nm][0] == "obj" and imported[m][nm][1] in defined and imported[m][nm][1] not in classes: tgt = imported[m][nm][1]
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                if f.value.id == "self" and "_" in owner:
                    cls = owner.split("_", 1)[0] if owner.split("_", 1)[0] in classes else None
                    for c in (mro(cls) if cls else []):
                        if f.attr in methods.get(c, ()): tgt = f"{c}_{f.attr}"; break
                elif f.value.id in imported[m] and imported[m][f.value.id][0] == "mod":
                    mm = imported[m][f.value.id][1]
                    if f.attr in funcs.get(mm, ()): tgt = f.attr
            if tgt and tgt != owner: calls.add((owner, tgt))
for m, t in trees.items():
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): visit_body(m, n.name, n)
        if isinstance(n, ast.ClassDef):
            for s in n.body:
                if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)): visit_body(m, f"{n.name}_{s.name}", s)
inherits = {(c, b) for c, (m, bs) in classes.items() for b in bs if b}
truth = {"defined in": sorted(defined.items()), "calls": sorted(calls), "raises": sorted(raises), "inherits from": sorted(inherits), "imports": sorted(imports)}
json.dump(truth, open(out, "w"), indent=0)
print({k: len(v) for k, v in truth.items()})
