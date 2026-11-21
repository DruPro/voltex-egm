"""Temporary layer: codebase analysis -> facts (studies/stress). Not part of the engine or the SDK.

Three extractors, three languages, three shapes of code fact:
  python(roots)   ast: is defined in, calls, inherits from, imports, raises, has method, is decorated by
  c_headers(root) regex: includes, declares type, has field of type, returns type, aliases
  js(roots)       regex: requires / imports, defines function, exports

Each returns (facts, stats). A fact is "subject relation object" with single-token names (letters, digits, _).
The answer key for a cell is a seeded share of these facts, held out by tools/bench.py; the engine never sees it.
Only names relative to each package root are used, never machine paths.
"""
import ast, os, re

TOK = re.compile(r"[^A-Za-z0-9_]")


def tok(s):
    s = TOK.sub("_", s).strip("_")
    return s or None


def _py_files(root, skip=("test", "tests", "idlelib", "lib2to3", "site-packages", "dist-packages")):
    for d, ds, fs in os.walk(root):
        ds[:] = sorted(x for x in ds if x not in skip and not x.startswith((".", "__pycache__")))
        for f in sorted(fs):
            if f.endswith(".py"): yield os.path.join(d, f)


def python(roots, max_lines=None):
    """roots: list of (root_dir, prefix). Module names are prefix + path inside root."""
    facts, lines_read, files = set(), 0, 0
    for root, prefix in roots:
        for p in _py_files(root):
            try: src = open(p, encoding="utf-8").read(); tree = ast.parse(src)
            except Exception: continue
            n = src.count("\n"); files += 1; lines_read += n
            rel = os.path.relpath(p, root)[:-3].replace(os.sep, ".")
            mod = tok(prefix + "__" + rel.replace(".", "__"))
            if not mod: continue
            local = {}
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    local[node.name] = tok(mod + "__" + node.name)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        t = tok(prefix + "__" + a.name.replace(".", "__"))
                        if t and t != mod: facts.add(f"{mod} imports {t}")
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    t = tok(prefix + "__" + node.module.replace(".", "__"))
                    if t and t != mod: facts.add(f"{mod} imports {t}")
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): continue
                me = local[node.name]
                if not me: continue
                facts.add(f"{me} is defined in {mod}")
                for d in getattr(node, "decorator_list", []):
                    nm = d.id if isinstance(d, ast.Name) else (d.attr if isinstance(d, ast.Attribute) else None)
                    if nm and tok(nm): facts.add(f"{me} is decorated by {tok('deco_' + nm)}")
                if isinstance(node, ast.ClassDef):
                    for b in node.bases:
                        if isinstance(b, ast.Name) and b.id in local and local[b.id] != me:
                            facts.add(f"{me} inherits from {local[b.id]}")
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and tok(sub.name):
                            facts.add(f"{me} has method {tok('meth_' + sub.name)}")
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in local:
                        if local[sub.func.id] != me: facts.add(f"{me} calls {local[sub.func.id]}")
                    elif isinstance(sub, ast.Raise) and sub.exc is not None:
                        e = sub.exc.func if isinstance(sub.exc, ast.Call) else sub.exc
                        if isinstance(e, ast.Name) and tok(e.id): facts.add(f"{me} raises {tok('exc_' + e.id)}")
            if max_lines and lines_read >= max_lines: break
    return sorted(facts), {"files": files, "lines": lines_read}


INC = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)
STRUCT = re.compile(r"\b(struct|union|enum)\s+([A-Za-z_]\w*)\s*\{([^{}]*)\}", re.S)
FIELD = re.compile(r"^\s*(?:const\s+|unsigned\s+|signed\s+|struct\s+|enum\s+|union\s+)*([A-Za-z_]\w*)[\s\*]+([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*;", re.M)
FUNC = re.compile(r"^\s*(?:extern\s+|static\s+|inline\s+|const\s+|unsigned\s+|struct\s+)*([A-Za-z_]\w*)[\s\*]+([A-Za-z_]\w*)\s*\([^;{)]*\)\s*(?:__\w+\s*(?:\([^)]*\))?\s*)*;", re.M)
TYPEDEF = re.compile(r"^\s*typedef\s+(?:struct\s+|union\s+|enum\s+|const\s+|unsigned\s+)*([A-Za-z_]\w*)[\s\*]+([A-Za-z_]\w*)\s*;", re.M)
CKEY = {"return", "if", "else", "while", "for", "sizeof", "typedef", "define", "do", "switch", "case"}


def c_headers(root, max_lines=None):
    facts, lines_read, files = set(), 0, 0
    for d, ds, fs in os.walk(root):
        ds.sort()
        for f in sorted(fs):
            if not f.endswith(".h"): continue
            p = os.path.join(d, f)
            try: src = open(p, encoding="utf-8", errors="replace").read()
            except Exception: continue
            files += 1; lines_read += src.count("\n")
            h = tok("h_" + os.path.relpath(p, root)[:-2])
            if not h: continue
            for m in INC.finditer(src):
                t = tok("h_" + m.group(1)[:-2] if m.group(1).endswith(".h") else "h_" + m.group(1))
                if t and t != h: facts.add(f"{h} includes {t}")
            for m in STRUCT.finditer(src):
                s = tok("t_" + m.group(2)); facts.add(f"{s} is declared in {h}"); facts.add(f"{s} is a {m.group(1)}")
                if m.group(1) != "enum":
                    for fm in FIELD.finditer(m.group(3)):
                        if fm.group(1) not in CKEY: facts.add(f"{s} has field of type {tok('t_' + fm.group(1))}")
            for m in FUNC.finditer(src):
                if m.group(1) in CKEY or m.group(2) in CKEY: continue
                fn = tok("f_" + m.group(2)); facts.add(f"{fn} is declared in {h}"); facts.add(f"{fn} returns {tok('t_' + m.group(1))}")
            for m in TYPEDEF.finditer(src):
                if m.group(1) not in CKEY: facts.add(f"{tok('t_' + m.group(2))} aliases {tok('t_' + m.group(1))}")
            if max_lines and lines_read >= max_lines: return sorted(facts), {"files": files, "lines": lines_read}
    return sorted(facts), {"files": files, "lines": lines_read}


REQ = re.compile(r"""(?:require\(\s*['"]([^'"]+)['"]\s*\)|^\s*import\s[^'"]*?from\s+['"]([^'"]+)['"]|^\s*import\s+['"]([^'"]+)['"])""", re.M)
JSFN = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(", re.M)
JSEXP = re.compile(r"^\s*(?:module\.)?exports\.([A-Za-z_$][\w$]*)\s*=|^\s*export\s+(?:const|let|var|class|function)\s+([A-Za-z_$][\w$]*)", re.M)


def _js_mod(path, root):
    rel = os.path.relpath(path, root)
    rel = re.sub(r"\.(c|m)?js$", "", rel)
    return tok("js_" + rel)


def js(roots, max_lines=None):
    facts, lines_read, files = set(), 0, 0
    for root in roots:
        for d, ds, fs in os.walk(root):
            ds[:] = sorted(x for x in ds if x not in ("test", "tests", "__tests__", "dist", "min") and not x.startswith("."))
            for f in sorted(fs):
                if not re.search(r"\.(c|m)?js$", f) or f.endswith(".min.js"): continue
                p = os.path.join(d, f)
                try: src = open(p, encoding="utf-8", errors="replace").read()
                except Exception: continue
                if len(src) > 400000: continue
                files += 1; lines_read += src.count("\n")
                me = _js_mod(p, root)
                if not me: continue
                for m in REQ.finditer(src):
                    t = m.group(1) or m.group(2) or m.group(3)
                    if t.startswith("."):
                        t = os.path.normpath(os.path.join(os.path.dirname(p), t)); t = _js_mod(t, root)
                    else:
                        t = tok("js_pkg_" + t)
                    if t and t != me: facts.add(f"{me} requires {t}")
                for m in JSFN.finditer(src):
                    fn = tok(me + "__" + m.group(1).replace("$", "S"))
                    if fn: facts.add(f"{fn} is defined in {me}")
                for m in JSEXP.finditer(src):
                    nm = (m.group(1) or m.group(2)).replace("$", "S")
                    if tok(nm): facts.add(f"{me} exports {tok('sym_' + nm)}")
                if max_lines and lines_read >= max_lines: return sorted(facts), {"files": files, "lines": lines_read}
    return sorted(facts), {"files": files, "lines": lines_read}
