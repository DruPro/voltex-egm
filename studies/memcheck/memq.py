"""memq: paste C code, ask whether a function leaks.

  python3 memq.py CODE.c [-I DIR ...] [--ask "FUNCTION is a ?"] ...    (no --ask: interactive prompt)
  cat code.c | python3 memq.py - -I include/                          (pasted code on stdin)

How it answers, and what it can't do:
  1. clang's parser turns the code into exact facts: where each pointer comes from, what it is passed to, how it
     ends, whether it is handed on (returned or stored).
  2. EGM learns the code's own conventions from those facts, e.g. "handles from ctx_create end with ctx_destroy",
     without being told which function is a destructor.
  3. A function is reported as a memory leak when one of its handles breaks a learned convention and isn't handed on.
     The verdict carries EGM's proof. It is a finding, not a guarantee:
       - "no leak found" means no learned convention is broken; it does not prove the function safe;
       - "not enough evidence" means the code doesn't use that handle's source often enough to learn a convention
         (a single pasted function can't teach EGM anything about the API it calls).
"""
import collections, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "spike1"), os.path.join(HERE, "..", "..")]
import egm      # noqa: E402
import extract  # noqa: E402

MIN_USES = 5    # a convention needs at least this many uses of the same source (EGM's own minimum support)


class Model:
    def __init__(self, path, args):
        self.facts = extract.extract(path, args)
        self.handles = collections.defaultdict(dict)          # function -> handle -> info
        src = {}; ends = {}; esc = collections.defaultdict(set)
        for l in self.facts:
            w = l.split()
            if " comes from " in l: src[w[0]] = w[-1]
            elif " ends with " in l: ends[w[0]] = w[-1]
            elif " escapes via " in l: esc[w[0]].add(w[-1])
        self.uses = collections.Counter(src.values())
        for h, s in src.items():
            fn, var = h.split("__", 1)
            self.handles[fn][h] = {"var": var, "source": s, "ends": ends.get(h), "escapes": esc[h] - {"none"}}
        self.e = egm.Engine(settings={"TREES": 1})
        self.e.ingest_many(self.facts)
        self.e.infer_all()
        self.conflict = {}
        for c in self.e.conflicts():
            if " ends with " in c.detail:
                expect = c.detail.split("inferred: ")[1].split(" |")[0].split()[-1]
                because = c.detail.split("because ", 1)[1].split("  [rule")[0]
                self.conflict[c.subject] = (expect, because)
        self.rules = [r for r in self.e.evidence() if "ends with ?](a," in r["rule"]]

    def verdict(self, fn):
        if fn not in self.handles and not any(l.startswith(fn + "__") for l in self.facts):
            known = sorted(self.handles)
            return f"{fn}: no pointer handles found in this function (or no such function). Functions with handles: {', '.join(known[:8])}{' ...' if len(known) > 8 else ''}"
        out, worst = [], "no leak found"
        for h, i in sorted(self.handles[fn].items()):
            if h in self.conflict and not i["escapes"]:
                expect, because = self.conflict[h]
                worst = "MEMORY LEAK"
                out.append(f"  '{i['var']}' from {i['source']}() ends with {i['ends']}(), but the code's convention is that it ends with {expect}()\n"
                           f"      because: {because}")
            elif i["escapes"]:
                out.append(f"  '{i['var']}' from {i['source']}() is handed on ({', '.join(sorted(i['escapes']))}): the caller owns it now")
            elif self.uses[i["source"]] < MIN_USES:
                if worst == "no leak found": worst = "not enough evidence"
                out.append(f"  '{i['var']}' from {i['source']}(): only {self.uses[i['source']]} use(s) of {i['source']}() in this code, too few to learn its convention")
            else:
                out.append(f"  '{i['var']}' from {i['source']}() ends with {i['ends']}(), consistent with how the rest of the code uses {i['source']}()")
        return f"{fn} is: {worst}\n" + "\n".join(out)

    def close(self):
        self.e.close()


def main(argv):
    asks = [argv[i + 1] for i in range(len(argv)) if argv[i] == "--ask"]
    rest = [a for i, a in enumerate(argv) if a != "--ask" and (i == 0 or argv[i - 1] != "--ask")]
    path, args = rest[0], rest[1:]
    if path == "-":
        f = tempfile.NamedTemporaryFile("w", suffix=".c", delete=False); f.write(sys.stdin.read()); f.close(); path = f.name
    m = Model(path, args)
    print(f"[memq] {len(m.facts)} facts from {sum(len(v) for v in m.handles.values())} handles in {len(m.handles)} functions")
    try:
        qs = asks or iter(lambda: input("memq> ").strip(), "")
        for q in qs:
            fn = q.split()[0] if q.split() else ""
            print(m.verdict(fn)); print()
    except EOFError:
        pass
    finally:
        m.close()


if __name__ == "__main__":
    main(sys.argv[1:])
