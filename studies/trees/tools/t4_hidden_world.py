"""H2 (no harm from longer chains) and H4 (conditions fix harvest) on the hidden world: 5 seeds x 30/50/70%, 4 configurations.
Reuses the Blind World study's observations, hidden truth and evaluator unchanged; the engine sees only obs files."""
import json, re, subprocess, sys
B = "/home/claude/work/blind"; sys.path.insert(0, B); sys.path.insert(0, B + "/hidden")
import lib
from evaluate import evaluate
E = __import__("os").environ.get("VOLTEX", "/home/claude/drupro/voltex-egm/build/voltex2")
CONFIGS = {"base": [], "trees": ["SET TREES 1"]}
PREM = re.compile(r"\[\? (.*?) \?\]\((\w),(\w)\)")

def rule_true_conf(text, T, preds):
    """True confidence of an accepted rule on the full hidden world: of the conclusions its body predicts, how many are true."""
    body, _, head = text.partition(" => ")
    cond = None
    if " if " in head:
        head, _, c = head.partition(" if "); m = re.match(r"\[\? (.*?) \?\]\((\w),(.*)\)", c); cond = (m.group(1), set(m.group(3).split("|")))
    prem = PREM.findall(body); hm = PREM.findall(head)
    if not hm or any(p[0] not in T for p in prem) or hm[0][0] not in T: return None
    hrel, hx, hy = hm[0]; truthT = set(map(tuple, T[hrel]))
    out = {}
    for rel, x, y in prem:
        d = {}
        for a, b in T[rel]: d.setdefault(a, []).append(b)
        out[(rel, x, y)] = d
    condsub = None
    if cond:
        condsub = {a for a, b in T[cond[0]] if b in cond[1]}
    # premises form a path over variables a,b,c,... (inverse: a,b => (b,a))
    preds_n = preds_k = 0
    if len(prem) == 1:
        rel, x, y = prem[0]
        for a, bs in out[prem[0]].items():
            for b in bs:
                if a == b: continue
                s, o = (b, a) if (hx, hy) == ("b", "a") else (a, b)
                if condsub is not None and s not in condsub: continue
                preds_n += 1; preds_k += (s, o) in truthT
    else:
        def walk(i, node, seen):
            if i == len(prem): yield node; return
            for nx in out[prem[i]].get(node, []):
                if nx in seen: continue
                yield from walk(i + 1, nx, seen | {nx})
        starts = set(out[prem[0]])
        for a in starts:
            if condsub is not None and a not in condsub: continue
            for e in set(walk(0, a, {a})):
                preds_n += 1; preds_k += (a, e) in truthT
    return preds_k / preds_n if preds_n else None

rows = []
for seed in range(5):
    T = json.load(open(f"{B}/hidden/truth_s{seed}.json"))["truth"]; preds = sorted(T, key=len, reverse=True)
    for cov in (30, 50, 70):
        tag = f"s{seed}_c{cov}"; info = json.load(open(f"{B}/hidden/info_{tag}.json"))
        observed = [tuple(f) for f in info["observed"]]; odepth = lib.oracle(observed)
        row = {"seed": seed, "coverage": cov}
        for name, sets in CONFIGS.items():
            cmds = "\n".join(sets + [f"INGESTFILE {B}/obs/obs_{tag}.txt", "RELATIONS", "INFER ALL", "EXIT"]) + "\n"
            txt = subprocess.run([E], input=cmds, capture_output=True, text=True).stdout
            open(f"logs/t4_{name}_{tag}.log", "w").write(txt)
            derived = set(filter(None, (lib.parse_fact(l.split("\t")[1], preds) for l in txt.splitlines() if l.startswith("FACT\t"))))
            ev = evaluate(derived, observed, info, T, odepth, preds, [], [], seed)
            acc = [l.strip()[7:].split("  n=")[0].strip() for l in txt.splitlines() if l.strip().startswith("ACCEPT")]
            confs = [(r, rule_true_conf(r, T, preds)) for r in acc]
            hv = ev["per_predicate"]["harvests"]
            row[name] = {"precision": ev["precision"], "recall": ev["recall"], "derived": ev["derived"], "wrong": ev["wrong"],
                         "harvest_correct": hv["derived"] - hv["wrong"], "harvest_wrong": hv["wrong"],
                         "rules": len(acc), "rules_valid": sum(1 for _, c in confs if c is not None and c >= 0.9),
                         "rules_unscored": sum(1 for _, c in confs if c is None),
                         "conditional_rules": [r for r in acc if " if " in r], "invalid_rules": [r for r, c in confs if c is not None and c < 0.9]}
        rows.append(row)
        print(tag, " | ".join(f"{n}: P={row[n]['precision']:.3f} R={row[n]['recall']:.3f} wrong={row[n]['wrong']} harvestW={row[n]['harvest_wrong']} rules={row[n]['rules']}({row[n]['rules_valid']} valid)" for n in CONFIGS), flush=True)
json.dump(rows, open("results_t4.json", "w"), indent=1)
