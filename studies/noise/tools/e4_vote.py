"""E4 VOTE: repeated noisy reports. company (scale 1) and hidden (scale 1, coverage 0.5); noise 0.15/0.30; reports 1/3/5;
seeds 0-4; configurations base, V, VQ, VRQ. Writes results_vote.jsonl."""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib

CONF = {"base": {}, "V": {"VOTE": 1}, "VQ": {"VOTE": 1, "QUARANTINE": 1}, "VRQ": {"VOTE": 1, "REPLICATE": 1, "QUARANTINE": 1}}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results_vote.jsonl")


def evidence_left(out, obs, hidden):
    """Corrupted reports that still take part as evidence: corrupted stated facts not outvoted or quarantined;
    and true stated facts that were outvoted or quarantined (harm)."""
    rels = sorted(hidden["relations"], key=len, reverse=True)
    T = {tuple(x) for x in hidden["truth"]}
    stated = lib.facts_of(open(obs).read().splitlines(), rels)
    removed = set()
    for l in out.splitlines():
        if l.startswith("CONFLICT\t") and ("OUTVOTED" in l or "QUARANTINED" in l):
            ft = l.split("\t")[3].split("stated: ", 1)[1].split(" | ")[0]
            f = lib.parse_fact(ft, rels)
            if f: removed.add(f)
    bad = {f for f in stated if f not in T}
    return {"wrong_evidence_stated": len(bad), "wrong_evidence_left": len(bad - removed), "true_removed": len(removed & T)}


def main():
    done = set()
    if os.path.exists(OUT):
        for l in open(OUT): d = json.loads(l); done.add((d["world"], json.dumps(d["params"], sort_keys=True), d["config"]))
    with open(OUT, "a") as f:
        for w in ("company", "hidden"):
            for nz in (0.15, 0.30):
                for rp in (1, 3, 5):
                    for s in range(5):
                        kw = dict(seed=s, scale=1.0, noise=nz, reports=rp) if w == "company" else dict(seed=s, scale=1, coverage=0.5, noise=nz, reports=rp)
                        obs, hid = lib.world(w, **kw)
                        for c in CONF:
                            key = (w, json.dumps(kw, sort_keys=True), c)
                            if key in done: continue
                            st = lib.settings_lines(CONF[c]); t = time.time()
                            out = lib.run(obs, st)
                            r = lib.score(out, obs, hid, with_causes=True, settings=st)
                            r.update(evidence_left(out, obs, hid))
                            r["fact_lines"] = sum(1 for l in out.splitlines() if l.startswith(("FACT\t", "CONFLICT\t")))
                            r["fact_lines_hash"] = hashlib.sha256("\n".join(l for l in out.splitlines() if l.startswith(("FACT\t", "CONFLICT\t"))).encode()).hexdigest()[:16]
                            r.update(world=w, params=kw, config=c, seconds=round(time.time() - t, 2))
                            f.write(json.dumps(r) + "\n"); f.flush()
                            print(w, kw, c, r["derived_new"], r["wrong"], round(r["precision"], 4), round(r["recall"], 4), r["wrong_evidence_left"], flush=True)


if __name__ == "__main__":
    main()
