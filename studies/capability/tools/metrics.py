"""Capability measures computed from a Run (interface.py) and a World (worlds.py). Rates with nothing to divide by are
None (undefined), never 1.0. Every rate is returned with its counts."""
from cworlds import stated


def measure(world, run):
    S = stated(world); T = world.truth; U = world.unseen
    conf = {}
    for a in run.answers:
        if a.status == "derived" and a.fact not in S:
            c = -1.0 if a.confidence is None else a.confidence
            conf[a.fact] = max(conf.get(a.fact, -1.0), c)
    new = set(conf)
    correct = new & T; wrong = new - T
    has_unseen = lambda f: f[1] in U or f[2] in U
    missing = {f for f in T - S if not has_unseen(f)}
    m = {
        # C3 deduction
        "new": len(new), "correct": len(correct), "wrong": len(wrong), "missing": len(missing),
        "precision": len(correct) / len(new) if new else None,
        "recall": len(correct & missing) / len(missing) if missing else None,
        # C4 abstention
        "invented_unseen": sum(1 for f in new if has_unseen(f)),
        # C1 retention
        "retention": (sum(run.retained.values()) / len(run.retained)) if run.retained else None,
        "retention_n": len(run.retained),
        # C12 cost
        "seconds": round(run.seconds, 3), "peak_mb": None if run.peak_mb is None else round(run.peak_mb, 1),
    }
    if world.undeterminable is not None:
        keys = world.undeterminable
        answered = {(f[0], f[1]) for f in new} & keys
        m["undet_queries"] = len(keys); m["undet_answered"] = len(answered)
        m["abstention"] = (1 - len(answered) / len(keys)) if keys else None
    else:
        m["undet_queries"] = None; m["undet_answered"] = None; m["abstention"] = None
    # C7 flags on injected corruptions that are stated
    cs = world.corrupted & S
    if cs:
        m["flag_precision"] = (len(run.flagged & cs) / len(run.flagged)) if run.flagged else None
        m["flag_recall"] = len(run.flagged & cs) / len(cs)
    else:
        m["flag_precision"] = None; m["flag_recall"] = None
    m["flagged"] = len(run.flagged); m["corrupted_stated"] = len(cs)
    # C5 risk-coverage over the engine's own ranking of its new answers (ties broken by fact text: deterministic)
    order = sorted(new, key=lambda f: (-conf[f], f))
    risks, hit, rec_hit = [], 0, 0
    p_at = {0.25: None, 0.5: None, 0.75: None}
    for k, f in enumerate(order, 1):
        hit += f in T; rec_hit += f in missing
        risks.append(1 - hit / k)
        if missing:
            r = rec_hit / len(missing)
            for lv in p_at:
                if p_at[lv] is None and r >= lv:
                    p_at[lv] = hit / k
    m["aurc"] = (sum(risks) / len(risks)) if risks else None
    for lv, v in p_at.items():
        m[f"p_at_r{int(lv * 100)}"] = v
    return m
