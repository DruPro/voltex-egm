"""Part 2 data: evidence files (plain / enriched), one question set, a hidden key, and EGM scripts. Seeds 41, 42."""
import sys, os, json, re
os.environ["LATE"] = "1"
_argv = sys.argv; sys.argv = sys.argv[:1]
src = open("/home/claude/work/evolve/exp_evo.py").read()
# 5 instances per scenario (keeps two-value subjects well under 10%); one department and two moved functions
src = src.replace("    n = 15; inst = []", "    n = 5; inst = []").replace("mgr_depts = rng.sample(D, 3)", "mgr_depts = rng.sample(D, 1)")
src = src.replace("inst = []; taken = set(); n = 15", "inst = []; taken = set(); n = 5").replace("for g in movers[:6]:", "for g in movers[:2]:")
src = src.replace("    free = [e for e in Em if e not in taken]; rng.shuffle(free); it = iter(free); n = 15", "    free = [e for e in Em if e not in taken]; rng.shuffle(free); it = iter(free); n = 5")
exec(src.rsplit("if __name__", 1)[0])
sys.argv = _argv
L = "/home/claude/work/egm22/llm"; H = "/home/claude/work/egm22/llm_hidden"
os.makedirs(L, exist_ok=True); os.makedirs(H, exist_ok=True)
NOUN = {"lives in": "where {x} lives", "is from": "which region {x} is from", "works as": "{x}'s profession", "works in": "which department {x} works in",
        "reports to": "who {x} reports to", "is managed by": "who manages {x}", "is defined in": "which module function {x} is defined in",
        "assigned to": "which projects {x} is assigned to", "volunteers at": "where {x} volunteers"}
ONEQ = {"lives in": "Where does {x} live now?", "is from": "Which region is {x} from now?", "works as": "What is {x}'s profession now?",
        "works in": "Which department does {x} work in now?", "reports to": "Who does {x} report to now?", "is managed by": "Who manages department {x} now?",
        "is defined in": "Which module is function {x} defined in now?"}
SETQ = {"lives in": "List every place {x} lives now.", "volunteers at": "List every place {x} volunteers at now.", "assigned to": "List every project {x} is assigned to now."}
HASQ = {"depends on": "Does function {x} depend on module {v} now?", "calls": "Does function {x} call function {v} now?", "knows": "Does {x} know {v} now?"}
HELDQ = {"lives in": "Has {x} ever lived in {v}?", "works as": "Has {x} ever worked as {v}?", "works in": "Has {x} ever worked in department {v}?",
         "is managed by": "Has department {x} ever been managed by {v}?", "assigned to": "Has {x} ever been assigned to project {v}?"}
FMT = {"one": "one value; or UNKNOWN if the evidence does not establish it; or CONFLICT if the evidence contains incompatible claims it cannot settle",
       "set": "a list of values; or UNKNOWN; or CONFLICT",
       "has": "YES, NO or UNKNOWN",
       "held": "CURRENT (true now), PAST (true before but not now), NEVER (never true, e.g. the record saying so was corrected or withdrawn) or UNKNOWN",
       "conflict": "YES or NO"}
PLAIN_HEAD = "# Evidence: facts, one per line, in the order they were received.\n"
ENR_HEAD = ("# Evidence: observations in the order they were received. Each line is one observation:\n"
            "#   [source=S record=K time=T revision=R scope] fact; fact; ...\n"
            "# source: who reported it. record: the record (entity) the observation describes. time: the time the observation describes.\n"
            "# revision: a higher revision for the same source, record and time replaces the earlier revision for that time (a correction).\n"
            "# scope: 'snapshot' = the complete set of facts the source holds for that record at that time; 'partial' = additional facts only.\n")
summary = []
for seed in [41, 42]:
    for wn in ["people", "database", "code"]:
        wd = WORLDS[wn](seed)
        rounds = max(len(i["obs"]) for i in wd["inst"])
        arrivals = [i["obs"][r] for r in range(rounds) for i in wd["inst"] if r < len(i["obs"])]
        allobs = wd["base"] + arrivals
        tag = f"{wn}_s{seed}"
        open(f"{L}/{tag}_plain.txt", "w").write(PLAIN_HEAD + "".join(T(f) + "\n" for o in allobs for f in o["facts"]))
        open(f"{L}/{tag}_enriched.txt", "w").write(ENR_HEAD + "".join(f"[source={o['src']} record={o['key']} time={o['t']} revision={o['rev']} {o['scope']}] " + "; ".join(T(f) for f in o["facts"]) + "\n" for o in allobs))
        qs, key = [], []
        for i in wd["inst"]:
            for (kind, rel, x, v, truth, ptag) in i["probes"]:
                qid = f"{tag}_q{len(qs) + 1}"
                if kind == "one": text = ONEQ[rel].format(x=x)
                elif kind == "set": text = SETQ[rel].format(x=x)
                elif kind == "has": text = HASQ[rel].format(x=x, v=v)
                elif kind == "held": text = HELDQ[rel].format(x=x, v=v)
                else: text = (f"Is there conflicting information about {x}?" if rel == "*" else f"Does the evidence contain incompatible claims about {NOUN[rel].format(x=x)}?")
                qs.append({"id": qid, "question": text, "answer_format": FMT[kind]})
                key.append({"id": qid, "sc": i["sc"], "kind": kind, "rel": rel, "x": x, "v": v, "truth": sorted(truth) if isinstance(truth, frozenset) else truth, "tag": ptag})
        json.dump(qs, open(f"{L}/{tag}_questions.json", "w"), indent=0)
        json.dump(key, open(f"{H}/{tag}_key.json", "w"), indent=1)
        # EGM scripts: plain = INGEST every fact in arrival order; enriched = OBSERVE every observation
        asks = ["RELATIONS", "INFER ALL", "CONFLICTS"] + [f"ASK ? {r} ?" for r in wd["rels"]]
        open(f"{H}/{tag}_egm_plain.cmds", "w").write("\n".join([f"INGEST {T(f)}" for o in allobs for f in o["facts"]] + asks + ["EXIT"]) + "\n")
        open(f"{H}/{tag}_egm_enriched.cmds", "w").write("\n".join([f"OBSERVE {o['src']} {o['key']} {o['t']} {o['rev']} {o['scope']} | " + " ; ".join(T(f) for f in o["facts"]) for o in allobs] + asks + ["EXIT"]) + "\n")
        json.dump({"preds": wd["preds"]}, open(f"{H}/{tag}_meta.json", "w"))
        summary.append((tag, len(allobs), sum(len(o["facts"]) for o in allobs), len(qs)))
for s in summary: print(s)
