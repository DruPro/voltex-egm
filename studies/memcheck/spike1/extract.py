"""Facts from C source, via clang's own parser (libclang). One entity per pointer variable a function holds.

  <handle> comes from <callee>        the pointer was initialised or assigned from a call
  <handle> is passed to <callee>      the pointer is an argument of a call
  <handle> escapes via <how>          return | field | none   (explicit: the parser sees the whole function)
  <callee> returns type <T>           from the callee's declaration (pointee type)
  <callee> is source of <handle>      the reverse of "comes from"
  <handle> ends with <callee>         the last call the pointer is passed to, in source order ("nothing" if none):
                                      one value per handle, so EGM can learn it as a value-like conclusion

Usage: python3 extract.py FILE.c [-I DIR ...] > facts.txt
"""
import sys
import clang.cindex as ci

K = ci.CursorKind


def refs(node):
    """Variables referenced anywhere under node."""
    out = set()
    for n in node.walk_preorder():
        if n.kind == K.DECL_REF_EXPR and n.referenced is not None and n.referenced.kind in (K.VAR_DECL, K.PARM_DECL):
            out.add(n.referenced.hash)
    return out


def callee(call):
    r = call.referenced
    return r.spelling if r is not None else None


def first_call(node):
    for n in node.walk_preorder():
        if n.kind == K.CALL_EXPR:
            return n
    return None


def facts_for(fn, out, rtypes):
    handles = {}   # var hash -> entity name
    def handle(var, src):
        if var.type.get_canonical().kind != ci.TypeKind.POINTER:
            return
        h = f"{fn.spelling}__{var.spelling}"
        handles[var.hash] = h
        out.add(f"{h} comes from {src}"); out.add(f"{src} is source of {h}")
    for n in fn.walk_preorder():
        if n.kind == K.VAR_DECL:
            init = [c for c in n.get_children()]
            call = first_call(init[-1]) if init else None
            if call is not None and callee(call):
                handle(n, callee(call)); rtypes.add(call.referenced)
        elif n.kind == K.BINARY_OPERATOR and [t.spelling for t in n.get_tokens()][1:2] == ["="]:
            lhs, rhs = list(n.get_children())
            call = first_call(rhs)
            if lhs.kind == K.DECL_REF_EXPR and call is not None and callee(call) and lhs.referenced is not None:
                handle(lhs.referenced, callee(call)); rtypes.add(call.referenced)
    escaped = {h: set() for h in handles.values()}
    last = {h: "nothing" for h in handles.values()}
    for n in fn.walk_preorder():
        if n.kind == K.CALL_EXPR and callee(n):
            for a in list(n.get_arguments()):
                for v in refs(a):
                    if v in handles:
                        out.add(f"{handles[v]} is passed to {callee(n)}"); last[handles[v]] = callee(n)
        elif n.kind == K.RETURN_STMT:
            for v in refs(n):
                if v in handles:
                    escaped[handles[v]].add("return")
        elif n.kind == K.BINARY_OPERATOR and [t.spelling for t in n.get_tokens()][1:2] != ["="]:
            pass
        if n.kind == K.BINARY_OPERATOR:
            ch = list(n.get_children())
            if len(ch) == 2 and ch[0].kind == K.MEMBER_REF_EXPR:
                for v in refs(ch[1]):
                    if v in handles:
                        escaped[handles[v]].add("field")
    for h, c in last.items():
        out.add(f"{h} ends with {c}")
    for h, how in escaped.items():
        for x in sorted(how) or ["none"]:
            out.add(f"{h} escapes via {x}")


def main():
    path, args = sys.argv[1], sys.argv[2:]
    tu = ci.Index.create().parse(path, args=args)
    out, rtypes = set(), set()
    for c in tu.cursor.get_children():
        if c.kind == K.FUNCTION_DECL and c.is_definition() and c.location.file and c.location.file.name == path:
            facts_for(c, out, rtypes)
    for d in rtypes:
        t = d.result_type.get_canonical()
        if t.kind == ci.TypeKind.POINTER:
            out.add(f"{d.spelling} returns type {t.get_pointee().spelling.replace('struct ', '').replace(' ', '_')}")
    print("\n".join(sorted(out)))


if __name__ == "__main__":
    main()
