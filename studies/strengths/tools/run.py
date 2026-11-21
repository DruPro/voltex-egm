"""Run the engine on the stdlib facts under one configuration and score against the complete truth.

  python3 run.py NAME [K=V ...]      writes ../results/NAME.json

Scoring: a derived fact that is not stated is correct if it is in truth.json (every true target fact and every base
fact), wrong otherwise. Recall per target relation is over the hidden facts (obs/key.txt). Also kept: accepted rules,
proof rounds, peak memory and time, and proof trees for sampled correct answers (deepest first).
"""
import collections, json, os, random, resource, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); STUDY = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(STUDY, "..", "..")); sys.path.insert(0, ROOT)
import egm  # noqa: E402
ROUND = os.environ.get("ROUND", "1")   # 2: obs_r2 -> results_r2; 3: obs_r2 + TENDENCYSTEPS 0 -> results_r3
OBS = os.path.join(STUDY, "obs" + ("_r2" if ROUND != "1" else "")); OUT = os.path.join(STUDY, "results" + ("" if ROUND == "1" else "_r" + ROUND))
if ROUND == "D":   # exploratory depth stress: obs_depth (extract.py --r2 --hide-sub 0.7), round 3 settings
    OBS = os.path.join(STUDY, "obs_depth"); OUT = os.path.join(STUDY, "results_depth"); BIN = os.path.join(ROOT, "build", "voltex2")
TARGETS = ("is a subclass of", "belongs to package", "binds" if ROUND == "1" else "is bound to")
BASE = {"MAXWORDS": 16200 if ROUND == "1" else 28500}   # step 1 of docs/CHOOSING_SETTINGS.md: distinct words + about 1,000
if ROUND in ("3", "D"): BASE["TENDENCYSTEPS"] = 0


def norm(s): return " ".join(s.split())
def relof(f): return f.split(" ", 1)[1].rsplit(" ", 1)[0]


def proof(e, fact, depth=0, seen=None):
    seen = seen if seen is not None else set()
    if depth > 8 or fact in seen: return {"fact": fact, "stated": None}
    seen.add(fact)
    for f in e.ask(fact.rsplit(" ", 1)[0] + " ?"):
        if norm(f.fact) == norm(fact):
            if f.status == "stated" or not f.because: return {"fact": fact, "stated": True}
            return {"fact": fact, "stated": False, "tier": f.tier, "rule": f.rule,
                    "because": [proof(e, b, depth + 1, seen) for b in f.because]}
    return {"fact": fact, "stated": None}


def main(name, settings):
    stated = {norm(l) for l in open(os.path.join(OBS, "facts.txt")) if l.strip()}
    key = {norm(l) for l in open(os.path.join(OBS, "key.txt")) if l.strip()}
    t = json.load(open(os.path.join(OBS, "truth.json"))); truth = set(t["base"]) | set(t["targets"])
    st = dict(BASE, **settings); t0 = time.time()
    with egm.open(os.path.join(OBS, "facts.txt"), settings=st, binary=BIN) as e:
        t1 = time.time(); facts = e.infer_all(); t2 = time.time()
        rules = e.rules(); chains = e.chains()
        rnd = {norm(c["fact"]): c.get("round") for c in chains}
        new = [f for f in facts if norm(f.fact) not in stated]
        ok = [f for f in new if norm(f.fact) in truth]
        rr = random.Random(7)
        deep = sorted(ok, key=lambda f: -(rnd.get(norm(f.fact)) or 0))
        samples = {}
        for r in TARGETS:
            pool = [f for f in deep if relof(norm(f.fact)) == r]
            pick = pool[:2] + rr.sample(pool[2:], min(2, max(0, len(pool) - 2)))
            samples[r] = [proof(e, f.fact) for f in pick]
        wrong = [f for f in new if norm(f.fact) not in truth]
        wrong_proofs = [proof(e, f.fact) for f in rr.sample(wrong, min(4, len(wrong)))]
    wall = time.time() - t0
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss // 1024
    newn = {norm(f.fact) for f in new}; okn = {norm(f.fact) for f in ok}
    per = {}
    for r in TARGETS + ("other",):
        isr = (lambda f: relof(f) == r) if r != "other" else (lambda f: relof(f) not in TARGETS)
        d = {f for f in newn if isr(f)}; c = {f for f in okn if isr(f)}; k = {f for f in key if isr(f)}
        per[r] = {"derived": len(d), "correct": len(c), "wrong": len(d) - len(c), "hidden": len(k),
                  "recovered": len(k & c), "precision": round(len(c) / len(d), 4) if d else None,
                  "recall": round(len(k & c) / len(k), 4) if k else None}
    out = {"name": name, "settings": st, "stated": len(stated), "hidden": len(key), "derived_new": len(newn),
           "correct": len(okn), "wrong": len(newn) - len(okn), "recovered": len(key & okn),
           "precision": round(len(okn) / len(newn), 4) if newn else None, "recall": round(len(key & okn) / len(key), 4),
           "per_relation": per, "build_s": round(t1 - t0, 1), "infer_s": round(t2 - t1, 1), "wall_s": round(wall, 1),
           "peak_rss_mb": rss,
           "rounds": dict(sorted(collections.Counter(rnd.get(f) for f in okn).items(), key=lambda x: (x[0] is None, x[0] or 0))),
           "rules": [{"text": x.text, "shape": x.shape, "tier": x.tier, "n": x.n, "k": x.k, "rate": x.rate, "lift": x.lift,
                      "known": x.known, "agree": x.agree} for x in rules],
           "proofs": samples, "proofs_wrong": wrong_proofs}
    os.makedirs(OUT, exist_ok=True); json.dump(out, open(os.path.join(OUT, name + ".json"), "w"), indent=1, default=str)
    print(f"{name}: P {out['precision']} R {out['recall']} new {len(newn)} wrong {out['wrong']} "
          + " ".join(f"[{r}: P {v['precision']} R {v['recall']}]" for r, v in per.items() if r != 'other')
          + f" other {per['other']['derived']} | {out['wall_s']} s {rss} MB", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], dict(a.split("=", 1) for a in sys.argv[2:]))
