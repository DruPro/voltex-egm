"""Shared-conditions study runner (PREREGISTRATION.md). Baseline arm (CONDITIONS 0) against the experiment arm
(CONDITIONS 1), same binary, worlds, seeds and tools.

  python3 run.py registered [--seeds N]     S1-S3, S6-S8: the registered worlds and the farmers problem
  python3 run.py heldout                    S4, S5: the independent generator's conditional worlds (seeds 2000-2004)
  python3 run.py report                     write REPORT.md from results/*.json
"""
import json, os, random, re, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(STUDY, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "studies", "capability", "tools")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
from interface import EGMAdapter, parse_fact  # noqa: E402
import cworlds, metamorphic, metrics  # noqa: E402

RES = os.path.join(STUDY, "results")
ARMS = {"baseline": {}, "experiment": {"CONDITIONS": 1}}
POLICIES = ["egm-default", "policy-strict", "policy-tendency"]
KEYS = ["precision", "recall", "new", "wrong", "aurc", "seconds", "proof_validity"]
COND = re.compile(r"^(?P<base>.+?) if \[(?P<tmpl>.+?)\]\((?P<var>[ab]),(?P<vals>[^)]*)\)$")


def adapter(arm, pol):
    st = ARMS[arm]
    return EGMAdapter(st) if pol == "egm-default" else EGMAdapter(st, policy=pol.split("-", 1)[1])


def conditional_rules(lines, settings, policy="tendency"):
    """Every accepted conditional rule, parsed: base rule, conclusion relation, condition relation and values, the
    condition's evidence, and the stratum of `policy` that admits it."""
    with egm.Engine(settings=settings) as e:
        e.ingest_many(lines); e.apply_policy(policy)
        out = []
        for l in e.cmd("RULES EVIDENCE"):
            if not l.startswith("EVIDENCE\t"):
                continue
            p = l.split("\t"); m = COND.match(p[2])
            if not m:
                continue
            kv = dict(x.split("=", 1) for x in p[3:] if "=" in x)
            concl = re.findall(r"=> \[\? (.+?) \?\]", m.group("base"))
            out.append({"rule": p[2], "conclusion": concl[0] if concl else "", "cond_relation": m.group("tmpl").replace("?", "").strip(),
                        "cond_values": sorted(m.group("vals").split("|")), "admit": kv.get("admit"),
                        "cond_z": float(kv["cond_z"]) if "cond_z" in kv else None, "agree": kv.get("agree"), "rel": kv.get("rel"),
                        "validation": kv.get("validation"), "cond_in": kv.get("cond_in"), "cond_out": kv.get("cond_out")})
        return out


def summary(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None
    return {"mean": statistics.mean(xs), "sd": statistics.stdev(xs) if len(xs) > 1 else 0.0, "min": min(xs), "max": max(xs), "n": len(xs)}


def registered(seeds):
    out = {"worlds": {}, "farmers": {}}
    for nm, *_ in cworlds.CATALOGUE:
        per = {arm: {p: [] for p in POLICIES} for arm in ARMS}; conds = {arm: [] for arm in ARMS}
        for s in range(seeds):
            w = cworlds.load(nm, s)
            for arm in ARMS:
                for pol in POLICIES:
                    per[arm][pol].append(metrics.measure(w, adapter(arm, pol).run(w.lines, w.rels, [])))
                conds[arm].append(conditional_rules(w.lines, ARMS[arm]))
        out["worlds"][nm] = {"per_seed": per, "conditional_rules": conds,
                             "summary": {arm: {p: {k: summary([m.get(k) for m in per[arm][p]]) for k in KEYS} for p in POLICIES} for arm in ARMS}}
        print(nm, "done", flush=True)
    # the farmers problem in detail: structure, condition evidence, proofs, renaming
    fp = []
    for s in range(seeds):
        w = cworlds.load("harvest", s)
        rules = conditional_rules(w.lines, ARMS["experiment"])
        target = [r for r in rules if r["conclusion"] == "harvests"]
        with egm.Engine(settings=ARMS["experiment"]) as e:
            e.ingest_many(w.lines); e.apply_policy("tendency")
            people = sorted({l.split()[0] for l in w.lines if " works as " in l})[:200]
            proofs = []
            for p in people:
                proofs += [f for f in e.ask(f"{p} harvests ?") if f.status == "inferred"]
                if len(proofs) >= 3:
                    break
        lines2, back = metamorphic.rename(w.lines, w.rels, 3000 + s)
        a = adapter("experiment", "policy-tendency")
        base = {x.fact for x in a.run(w.lines, w.rels, []).answers}
        ren = {m for m in (back(x.fact) for x in a.run(lines2, w.rels, []).answers) if m and None not in m}
        fp.append({"seed": s, "target_rules": target,
                   "structure_correct": any(r["cond_relation"] == "works as" and r["cond_values"] == ["farmer", "miner"] for r in target),
                   "proof_examples": [{"fact": f.fact, "because": f.because, "rule": f.rule, "tier": f.tier, "weakest": f.weakest} for f in proofs[:3]],
                   "proofs_name_condition": all(" if [? works as ?]" in f.rule for f in proofs) if proofs else False,
                   "rename_jaccard": metamorphic.compare(base, ren)})
    out["farmers"] = fp
    return out


def heldout():
    sys.path.insert(0, os.path.join(ROOT, "studies", "sealed"))
    import gen_sealed  # noqa: E402  (written independently: studies/sealed)
    res = {}
    for struct in ("conditional", "conditional_control", "conditional_decoy"):
        rows = []
        for seed in range(2000, 2005):
            lines, key = gen_sealed.world(struct, seed)
            rels = key["relations"]; truth = {tuple(x) for x in key["truth"]}
            rules = conditional_rules(lines, ARMS["experiment"])
            run = adapter("experiment", "policy-tendency").run(lines, rels, [])
            S = {f for f in (parse_fact(l, sorted(rels, key=len, reverse=True)) for l in lines) if f}
            new = {a.fact for a in run.answers} - S
            row = {"seed": seed, "conditional_rules": rules, "new": len(new), "correct": len(new & truth)}
            conds = key.get("conditions") or []
            if conds:
                c = conds[0]
                target_rel = None
                for r in rules:
                    if r["cond_relation"] == c["condition_relation"]:
                        target_rel = r
                row["condition"] = c
                row["recovered"] = any(r["cond_relation"] == c["condition_relation"] and set(r["cond_values"]) == set(c["qualifying_values"]) for r in rules)
                concl = {r["conclusion"] for r in rules if r["cond_relation"] == c["condition_relation"]}
                cnew = {f for f in new if f[0] in concl}
                row["conditional_new"] = len(cnew); row["conditional_correct"] = len(cnew & truth)
                row["conditional_precision"] = len(cnew & truth) / len(cnew) if cnew else None
                row["decoy_chosen"] = any(r["cond_relation"] != c["condition_relation"] for r in rules)
            else:
                row["spurious_conditions"] = len(rules)
            row["precision_all"] = len(new & truth) / len(new) if new else None
            rows.append(row)
        res[struct] = rows
        print(struct, "done", flush=True)
    return res


def fmt(S, k):
    x = S.get(k)
    return "undef." if x is None else (f"{x['mean']:.3f}" if x["sd"] == 0 else f"{x['mean']:.3f} ± {x['sd']:.3f}")


def report():
    R = json.load(open(os.path.join(RES, "registered.json")))
    H = json.load(open(os.path.join(RES, "heldout.json"))) if os.path.exists(os.path.join(RES, "heldout.json")) else None
    L = ["# Shared evaluation of conditions: results", "",
         "Generated by `tools/run.py report` from `results/*.json`; do not edit by hand. Pre-registration: `PREREGISTRATION.md` "
         f"(sha256 in `prereg_hash.txt`). Seeds 0-{len(R['farmers']) - 1} for registered worlds; 2000-2004 for held-out worlds.", ""]
    # verdicts
    fp = R["farmers"]; hv = R["worlds"]["harvest"]["summary"]["experiment"]["policy-tendency"]
    hseeds = R["worlds"]["harvest"]["per_seed"]["experiment"]["policy-tendency"]
    s1 = hv["precision"] and hv["precision"]["mean"] >= 0.95 and hv["recall"]["mean"] >= 0.9 and all((m["precision"] or 0) >= 0.9 for m in hseeds)
    s2 = sum(f["structure_correct"] for f in fp); s3 = sum(1 for f in fp if f["target_rules"] and max((r["cond_z"] or 0) for r in f["target_rules"]) >= 3 and f["proofs_name_condition"])
    s6 = sum(1 for f in fp if f["rename_jaccard"] == 1.0)
    reg_fail, cost_fail = [], []
    for nm, W in R["worlds"].items():
        if nm == "harvest":
            continue
        for p in POLICIES:
            b, x = W["summary"]["baseline"][p], W["summary"]["experiment"][p]
            for k in ("precision", "recall", "aurc"):
                if b[k] is None and x[k] is None:
                    continue
                if (b[k] is None) != (x[k] is None):
                    reg_fail.append(f"{nm} {p} {k}: {fmt(b, k)} -> {fmt(x, k)}"); continue
                tol = 2 * b[k]["sd"]; d = x[k]["mean"] - b[k]["mean"]
                worse = d < -tol - 1e-9 if k != "aurc" else d > tol + 1e-9
                if worse:
                    reg_fail.append(f"{nm} {p} {k}: {fmt(b, k)} -> {fmt(x, k)}")
            if x["seconds"]["mean"] > 1.5 * b["seconds"]["mean"] and x["seconds"]["mean"] > 0.05:
                cost_fail.append(f"{nm} {p}: {b['seconds']['mean']:.2f} s -> {x['seconds']['mean']:.2f} s")
    L += ["## Verdicts", "", "| ID | Result | Detail |", "|---|---|---|"]
    L.append(f"| S1 farmers problem | {'pass' if s1 else 'FAIL'} | tendency with conditions: precision {fmt(hv, 'precision')}, recall {fmt(hv, 'recall')} (baseline: {fmt(R['worlds']['harvest']['summary']['baseline']['policy-tendency'], 'precision')} / {fmt(R['worlds']['harvest']['summary']['baseline']['policy-tendency'], 'recall')}) |")
    L.append(f"| S2 structure recognised | {'pass' if s2 == len(fp) else 'FAIL'} | correct condition (job in farmer, miner) in {s2} of {len(fp)} seeds |")
    L.append(f"| S3 condition distinguished | {'pass' if s3 == len(fp) else 'FAIL'} | cond_z >= 3 and proofs naming rule + condition in {s3} of {len(fp)} seeds |")
    if H:
        c = H["conditional"]; rec = sum(1 for r in c if r.get("recovered") and (r.get("conditional_precision") or 0) >= 0.9)
        ctrl = sum(1 for r in H["conditional_control"] if r.get("spurious_conditions", 0) == 0)
        dec = sum(1 for r in H["conditional_decoy"] if r.get("recovered") and not r.get("decoy_chosen"))
        L.append(f"| S4 generalization | {'pass' if rec >= 4 else 'FAIL'} | condition recovered with conditional precision >= 0.9 in {rec} of {len(c)} held-out worlds |")
        L.append(f"| S5 no spurious condition | {'pass' if ctrl >= 4 and dec >= 4 else 'FAIL'} | control: none in {ctrl} of 5; decoy: right condition, decoy not chosen in {dec} of 5 |")
    else:
        L.append("| S4, S5 | not run | the independent generator was not available yet |")
    L.append(f"| S6 vocabulary independence | {'pass' if s6 == len(fp) else 'FAIL'} | renamed harvest identical in {s6} of {len(fp)} seeds |")
    L.append(f"| S7 no regression | {'pass' if not reg_fail else 'FAIL'} | {'; '.join(reg_fail) if reg_fail else 'every world and policy within 2 sd of baseline'} |")
    L.append(f"| S8 cost | {'pass' if not cost_fail else 'FAIL'} | {'; '.join(cost_fail) if cost_fail else 'within 1.5x everywhere'} |")
    L += ["", "## Registered worlds, baseline vs experiment", "",
          "| World | Policy | Precision | Recall | AURC | Seconds | Conditional rules (experiment, per seed) |", "|---|---|---|---|---|---|---|"]
    for nm, W in R["worlds"].items():
        nconds = [len(x) for x in W["conditional_rules"]["experiment"]]
        for p in POLICIES:
            b, x = W["summary"]["baseline"][p], W["summary"]["experiment"][p]
            L.append(f"| {nm} | {p} | {fmt(b, 'precision')} → {fmt(x, 'precision')} | {fmt(b, 'recall')} → {fmt(x, 'recall')} | "
                     f"{fmt(b, 'aurc')} → {fmt(x, 'aurc')} | {fmt(b, 'seconds')} → {fmt(x, 'seconds')} | {nconds if p == 'egm-default' else ''} |")
    L += ["", "## Conditional rules proposed on every registered world (experiment arm)", "",
          "| World | Per seed | Conclusion, condition relation, admitting stratum |", "|---|---|---|"]
    for nm, W in R["worlds"].items():
        c = W["conditional_rules"]["experiment"]
        kinds = sorted({(r["conclusion"], r["cond_relation"], r["admit"]) for x in c for r in x})
        L.append(f"| {nm} | {[len(x) for x in c]} | {'; '.join(f'{a} if {b} ({d})' for a, b, d in kinds) or 'none'} |")
    L += ["", "## Farmers problem: what was learned", ""]
    for f in fp:
        L.append(f"- Seed {f['seed']}: " + "; ".join(f"`{r['rule']}` (admitted: {r['admit']}, {r['validation']}, cond_z {r['cond_z']}, inside {r['cond_in']}, outside {r['cond_out']})" for r in f["target_rules"]))
    if fp and fp[0]["proof_examples"]:
        L += ["", "A proof (seed 0, policy tendency):", "", "```"]
        for e in fp[0]["proof_examples"][:2]:
            L.append(f"{e['fact']}  [{e['tier']}, weakest {e['weakest']}]  because {' + '.join(e['because'])}  rule: {e['rule']}")
        L.append("```")
    if H:
        L += ["", "## Held-out conditional worlds (independent generator)", "", "| Structure | Seed | Learned conditional rules | Recovered | Conditional precision |", "|---|---|---|---|---|"]
        for st, rows in H.items():
            for r in rows:
                rules = "; ".join(f"{x['conclusion']} if {x['cond_relation']} in {x['cond_values']}" for x in r["conditional_rules"]) or "none"
                cp = r.get("conditional_precision")
                L.append(f"| {st} | {r['seed']} | {rules} | {r.get('recovered', '–')} | {'undef.' if cp is None else f'{cp:.3f}'} |")
    open(os.path.join(STUDY, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print("wrote REPORT.md")


if __name__ == "__main__":
    a = sys.argv[1:]; os.makedirs(RES, exist_ok=True)
    if a[0] == "registered":
        seeds = int(a[a.index("--seeds") + 1]) if "--seeds" in a else 5
        json.dump(registered(seeds), open(os.path.join(RES, "registered.json"), "w"), indent=1)
    elif a[0] == "heldout":
        json.dump(heldout(), open(os.path.join(RES, "heldout.json"), "w"), indent=1)
    elif a[0] == "report":
        report()
