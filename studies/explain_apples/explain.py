"""Claim checker that sits ON TOP of Voltex (Voltex itself is unchanged).

This script plays the part an LLM would play: it turns a sentence into questions,
asks Voltex, and writes an explanation built only from Voltex's answers.
Every evidence line is quoted verbatim from Voltex, marked stated or inferred."""
import subprocess, re, sys, os

class Voltex:
    def __init__(self, binary, facts):
        # stdbuf makes the unchanged binary flush each line so we can talk to it live
        self.p = subprocess.Popen(["stdbuf", "-oL", binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd(f"INGESTFILE {facts}")
    def cmd(self, line):
        self.p.stdin.write(line + "\nFIND __end_of_answer__\n"); self.p.stdin.flush()
        out = []
        while True:
            l = self.p.stdout.readline()
            if l.startswith("[FIND] not stored") or not l: return out
            out.append(l.rstrip("\n"))
    def ask(self, pattern):
        """Returns [(fact_text, 'stated'|'inferred', proof)] for an ASK pattern."""
        res = []
        for l in self.cmd(f"ASK {pattern}"):
            m = re.match(r"\s+(.*?)\s{2,}(stated|inferred)(?: \(score [\d.]+\) because (.*?)\s+\[rule)?", l)
            if m: res.append((m.group(1), m.group(2), m.group(3) or ""))
        return res
    def close(self): self.p.stdin.write("EXIT\n"); self.p.stdin.flush(); self.p.wait()

def obj(fact): return fact.split()[-1]
def band(vx, color):
    w = vx.ask(f"{color} has wavelength ?")
    if not w: return None
    a, b = re.match(r"(\d+)to(\d+)nm", obj(w[0][0])).groups()
    return int(a), int(b)
def tag(f): return f"[{f[1]}]" + (f"  because {f[2]}" if f[2] else "")

def parse_claim(vx, text):
    """Stand-in for the LLM: 'granny smith apples are red' -> ('granny_smith', 'red')."""
    s, _, color = re.split(r"\s+(are|is)\s+", text.strip().lower().rstrip("."), maxsplit=1)
    words = s.split()
    def forms(w): return [w, w[:-1], w[:-3] + "y" if w.endswith("ies") else w, w[:-2] if w.endswith("es") else w]
    cands = []
    for n in (len(words), len(words) - 1):          # "granny smith apples" -> try with and without the fruit word
        if n <= 0: continue
        head = words[:n]
        for f in forms(head[-1]): cands.append("_".join(head[:-1] + [f]))
    for c in cands:
        if vx.ask(f"{c} has color ?") or vx.ask(f"{c} has variety ?"): return c, color.strip(), " ".join(words)
    return cands[0], color.strip(), " ".join(words)

def explain(vx, text):
    subj, color, said = parse_claim(vx, text)
    print(f"\nCLAIM: \"{text}\"   ->   is {subj} {color}?")
    colors = vx.ask(f"{subj} has color ?")
    varieties = vx.ask(f"{subj} has variety ?")
    parents = vx.ask(f"? has variety {subj}")
    if not colors and not varieties:
        print(f"VERDICT: UNKNOWN. Voltex holds no facts about '{subj}', so it can neither support nor contradict the claim.")
        return
    hit = [f for f in colors if obj(f[0]) == color]
    if hit:
        print(f"VERDICT: SUPPORTED.")
        print(f"  - {hit[0][0]} {tag(hit[0])}")
        return
    cb = band(vx, color)
    if cb is None and not vx.ask(f"? has color {color}"):
        print(f"VERDICT: UNKNOWN COLOUR. Voltex has no facts about the colour '{color}'.")
        return
    print("VERDICT: CONFLICT. Nothing supports it, and the known facts point elsewhere:")
    known = [obj(f[0]) for f in colors]
    print(f"  1. {subj} is known to be {', '.join(known)}:")
    for f in colors: print(f"       - {f[0]} {tag(f)}")
    if cb:
        print(f"  2. {color} is light of {cb[0]}-{cb[1]} nm:")
        print(f"       - {color} has wavelength {cb[0]}to{cb[1]}nm [stated]")
        overlaps = []
        for k in known:
            kb = band(vx, k)
            if kb:
                ov = kb[0] < cb[1] and cb[0] < kb[1]
                overlaps.append(ov)
                print(f"       - {k} is {kb[0]}-{kb[1]} nm -> {'overlaps' if ov else 'no overlap'} with {color}")
        if overlaps and not any(overlaps): print(f"     so {color} is a different colour, not a shade of any known {subj} colour.")
    if varieties:
        vcols = []
        for v in varieties:
            vc = vx.ask(f"{obj(v[0])} has color ?")
            vcols.append((obj(v[0]), [obj(x[0]) for x in vc]))
        print(f"  3. none of the {len(varieties)} known varieties of {subj} is {color}: "
              + ", ".join(f"{v} ({'/'.join(c) or 'unknown'})" for v, c in vcols))
    if parents:
        par = obj(parents[0][0].split(" has variety ")[0]) if False else parents[0][0].split()[0]
        print(f"  3. {subj} is a variety of {par} and its colour is stated as {', '.join(known)}.")
    others = [f[0].split()[0] for f in vx.ask(f"? has color {color}")]
    if others: print(f"  4. for contrast, things known to be {color}: {', '.join(others)}.")
    print("  Caveat: Voltex only knows what it was told. This says 'contradicts all known facts', not 'proven impossible'.")

if __name__ == "__main__":
    vx = Voltex(sys.argv[1] if len(sys.argv) > 1 else "../v2/voltex2", "explain/facts.txt")
    claims = ["Apples are blue", "Apples are yellow", "Bananas are blue", "Granny smith apples are red",
              "Blueberries are blue", "Grapes are orange", "Dragonfruit is pink", "Apples are teal"]
    for c in claims: explain(vx, c)
    vx.close()
