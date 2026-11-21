"""Turns real Python standard-library code into facts for Voltex.

  f delegates to g   f has `return g(...)`            (the result of g IS f's result)
  f calls g          f calls g but does not return it   (decoy: calling is not returning)
  f returns T        from the official type stubs (typeshed), simplified to the base type

Half the functions' return types are hidden; the experiment asks Voltex to recover them."""
import ast, os, glob, json, random, collections
import mypy
STUBS = os.path.join(os.path.dirname(mypy.__file__), "typeshed", "stdlib")
SRC = "/usr/lib/python3.12"
os.makedirs("data", exist_ok=True)

def simple_type(node, cls):
    if node is None: return None
    if isinstance(node, ast.Constant) and node.value is None: return "none"
    if isinstance(node, ast.Name):
        if node.id in ("Any", "object", "NoReturn", "Never", "Incomplete"): return None
        if node.id == "Self": return cls.lower() if cls else None
        return node.id.lower() if node.id in ("None",) else node.id
    if isinstance(node, ast.Subscript):
        base = simple_type(node.value, cls)
        return None if base in ("Literal", "Optional", "Union", "Generator", "Iterator", "Iterable", "TypeGuard", "TypeIs") else base
    if isinstance(node, ast.Attribute): return node.attr
    return None   # unions and anything fancier are skipped

def stub_returns(mod):
    path = os.path.join(STUBS, mod + ".pyi")
    if not os.path.exists(path): return {}
    out = collections.defaultdict(set)
    tree = ast.parse(open(path).read())
    typevars = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                and getattr(n.value.func, "id", getattr(n.value.func, "attr", "")) in ("TypeVar", "ParamSpec") for t in n.targets if isinstance(t, ast.Name)}
    def visit(body, cls):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[(cls, n.name)].add(simple_type(n.returns, cls))
            elif isinstance(n, ast.ClassDef) and cls is None: visit(n.body, n.name)
            elif isinstance(n, ast.If): visit(n.body, cls); visit(n.orelse, cls)   # version-conditional stubs
    visit(tree.body, None)
    return {k: next(iter(v)) for k, v in out.items() if len(v) == 1 and None not in v and next(iter(v)) not in typevars and next(iter(v)) != "AnyStr"}   # skip overloads / unknown

facts = collections.defaultdict(set); returns_truth = {}; fn_count = 0
for path in sorted(glob.glob(f"{SRC}/*.py")):
    mod = os.path.basename(path)[:-3]
    if mod.startswith("_") or mod == "this": continue
    try: tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception: continue
    stubs = stub_returns(mod)
    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    classes = {n.name: {m.name for m in n.body if isinstance(m, ast.FunctionDef)} for n in tree.body if isinstance(n, ast.ClassDef)}
    def qn(cls, name): return f"{mod}__{cls}__{name}" if cls else f"{mod}__{name}"
    def resolve(call, cls):
        f = call.func
        if isinstance(f, ast.Name) and f.id in top: return qn(None, f.id)
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "self" and cls and f.attr in classes[cls]: return qn(cls, f.attr)
        return None
    def handle(fn, cls):
        global fn_count
        fn_count += 1; me = qn(cls, fn.name)
        returned = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
                t = resolve(node.value, cls)
                if t and t != me: facts["delegates to"].add((me, t)); returned.add(id(node.value))
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and id(node) not in returned:
                t = resolve(node, cls)
                if t and t != me: facts["calls"].add((me, t))
        if (cls, fn.name) in stubs: returns_truth[me] = stubs[(cls, fn.name)]
    for n in tree.body:
        if isinstance(n, ast.FunctionDef): handle(n, None)
        elif isinstance(n, ast.ClassDef):
            for m in n.body:
                if isinstance(m, ast.FunctionDef): handle(m, n.name)

r = random.Random(5)
fns = sorted(returns_truth); r.shuffle(fns)
hidden = set(fns[: len(fns) // 2])
lines = [f"{a} {rel} {b}" for rel in ("delegates to", "calls") for a, b in sorted(facts[rel])]
lines += [f"{f} returns {t}" for f, t in sorted(returns_truth.items()) if f not in hidden]
r.shuffle(lines)
open("data/code_facts.txt", "w").write("\n".join(lines) + "\n")
json.dump({"returns": returns_truth, "hidden": sorted(hidden),
           "delegates": sorted(facts["delegates to"]), "calls": sorted(facts["calls"])}, open("data/code_truth.json", "w"))
# how many hidden types are reachable at all through a delegation chain?
deleg = collections.defaultdict(set)
for a, b in facts["delegates to"]: deleg[a].add(b)
reach = sum(1 for f in hidden if any(g in returns_truth for g in deleg[f]))
print(f"functions scanned {fn_count} | with stub return type {len(returns_truth)} | delegations {len(facts['delegates to'])} "
      f"| plain calls {len(facts['calls'])} | stated facts {len(lines)} | hidden return types {len(hidden)} "
      f"| hidden ones that delegate to a typed function {reach}")
